#include <linux/limits.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <fcntl.h>
#include <pwd.h>

#include "../parser/ast.h"
#include "shell.h"

#define PIPE_RD 00
#define PIPE_WR 01
#define RE_CD   10
#define RE_ENV  11
#define RE_JOB  12

pid_t pid_g = -1;

void handle_sigstp(int sig) {
    sig--;
    if (pid_g > 0) {
        kill(pid_g, SIGTSTP);
    } else
        return;

    printf("Stop: %d\n", pid_g);
}

int handle_builtin(node_t* node) {
    if (!strcmp(node->command.program, "cd")) {
        if (chdir(node->command.argv[1]) == -1) {
            perror("cd error"); // change to try catch later;
            return -1;
        } else {
            return RE_CD; // match cd
        }
    } else if (!strcmp(node->command.program, "set")) {
        putenv(node->command.argv[1]);
        return RE_ENV;

    } else if (!strcmp(node->command.program, "unset")) {
        unsetenv(node->command.argv[1]);
        return RE_ENV;

    } else if (!strcmp(node->command.program, "exit")) {
        exit(atoi(node->command.argv[1]));

    } else if (!strcmp(node->command.program, "fg")) {
        if (pid_g > 0)
            if (kill(pid_g, SIGCONT)<0)
                perror("CONT");
        waitpid(pid_g, NULL, WSTOPPED);
        return RE_JOB;

    } else if (!strcmp(node->command.program, "bg")) {
        if (pid_g > 0)
            if (kill(pid_g, SIGCONT)<0)
                perror("CONT");
        waitpid(pid_g, NULL, WNOHANG);
        return RE_JOB;
    }
    return 0; // no match
}

int handle_cmd(node_t *node) {
    if (!handle_builtin(node)) {
        pid_t pid = fork();
        if (pid == 0) { // child
            setpgrp();
            execvp(node->command.program, node->command.argv);
            perror("### Simple cmd error");
            exit(1);
        } else {
            if (pid_g < 0)
                pid_g = pid;

            int status;
            signal(SIGTSTP, handle_sigstp);
            waitpid(pid, &status, WSTOPPED);
            return WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
        }
    }

    return 0;
}

void handle_seq (node_t *node) {
    if (node->type != NODE_SEQUENCE) {
        run_command(node);
    } else {
        run_command(node->sequence.first);
        handle_seq(node->sequence.second);
    }
}

typedef struct {
    pid_t pid;
    int providefd;
} subprocess_t;

subprocess_t subprocess(node_t *node) {
    int fds[2];
    pipe(fds);
    subprocess_t subp = {fork(), fds[1]};

    if (subp.pid == 0) { // child
        close(fds[PIPE_WR]); // no need write end
        dup2(fds[PIPE_RD], STDIN_FILENO);
        close(fds[PIPE_RD]); // already duplicated

        run_command(node);
        exit(0); // for built-ins
    } else {
        pid_g = subp.pid;
        signal(SIGTSTP, SIG_IGN);
    }

    close(fds[PIPE_RD]);
    return subp;
}

void handle_pipe(node_t* node) {
    int num_parts = node->pipe.n_parts;

    pid_t first_child = fork();
    if (first_child == 0) {

        int i;
        for (i = 0; i < num_parts-1; i++) { // child handles first (n-1) cmds;
            int fds[2];
            pipe(fds);

            if (!(fork())) { // grandchild
                close(fds[PIPE_RD]);    // no need the read end;
                dup2(fds[PIPE_WR], STDOUT_FILENO); // write to pipe[1]
                close(fds[PIPE_WR]);

                run_command(node->pipe.parts[i]);
                exit(0);
            }

            close(fds[PIPE_WR]);
            dup2(fds[PIPE_RD], STDIN_FILENO); // redirect the next childe to read from pipe;
            close(fds[PIPE_RD]);
            waitpid(-1, NULL, WNOHANG);
        }

        run_command(node->pipe.parts[i]);
        exit(0);
    } else { // grandpa handle the last cmd and does house-keeping
        while (waitpid(-1, NULL, 0) >= 0) {} // change to reap_children() later;
    }
}

void handle_redirect(node_t* node) {
    int fh = -1;
    int num_read = -1;
    char buffer[ARG_MAX];
    int fds[2];

    switch (node->redirect.mode) {
    case REDIRECT_INPUT:
        pipe(fds);

        fh = open(node->redirect.target, O_RDONLY | O_CREAT, 0777);
        if (fh < 0)
            perror("File open");
        num_read = read(fh, buffer, ARG_MAX);
        if (num_read < 0)
            perror("File read");

        subprocess_t subp = subprocess(node->redirect.child);
        dprintf(subp.providefd, "%s", buffer);
        close(subp.providefd);
        waitpid(subp.pid, NULL, 0);
        break;

    case REDIRECT_OUTPUT:
    case REDIRECT_APPEND:
    case REDIRECT_DUP:
        if (!fork()) {
            if (node->redirect.mode == REDIRECT_OUTPUT)
                fh = open(node->redirect.target, O_WRONLY | O_CREAT | O_TRUNC, 0777);
            else if (node->redirect.mode == REDIRECT_APPEND)
                fh = open(node->redirect.target, O_WRONLY | O_CREAT | O_APPEND, 0777);
            else
                fh = STDOUT_FILENO;

            if (fh < 0)
                perror("File open");

            dup2(fh, node->redirect.fd);

            if (strlen(node->redirect.child->command.program) == 0)
                dup2(fh, STDERR_FILENO);
            else if (node->redirect.mode == REDIRECT_DUP)
                dup2(STDOUT_FILENO, STDERR_FILENO);

            run_command(node->redirect.child);
            exit(0);
        } else {
            waitpid(-1, NULL, 0);
            if (fh > 0)
                close(fh);
        }
        break;

    default:
        break;
    }
}

char* str_replace(char* string, const char* substr, const char* replacement) {
    char* tok = NULL;
    char* newstr = NULL;
    char* oldstr = NULL;
    int   oldstr_len = 0;
    int   substr_len = 0;
    int   replacement_len = 0;

    newstr = strdup(string);
    substr_len = strlen(substr);
    replacement_len = strlen(replacement);

    while ((tok = strstr(newstr, substr))) {
        oldstr = newstr;
        oldstr_len = strlen(oldstr);
        newstr = (char*)malloc(sizeof(char) * (oldstr_len - substr_len + replacement_len + 1));

        if (newstr == NULL) {
            free(oldstr);
            return NULL;
        }

        memcpy(newstr, oldstr, tok - oldstr);
        memcpy(newstr + (tok - oldstr), replacement, replacement_len);
        memcpy(newstr + (tok - oldstr) + replacement_len, tok + substr_len, oldstr_len - substr_len - (tok - oldstr));
        memset(newstr + oldstr_len - substr_len + replacement_len, 0, 1);

        if (oldstr)
            free(oldstr);
    }
    return newstr;
}

void handle_prompt(char* ps1) {
    if (!ps1) {
        prompt = "vush$ ";
        return;
    }

    char hostname[1024];
    char work_dir[PATH_MAX];
    struct passwd *p = getpwuid(getuid());
    char* username = p->pw_name;

    hostname[1023] = '\0';
    gethostname(hostname, 1023);
    getcwd(work_dir, PATH_MAX);

    prompt = ps1;
    prompt = str_replace(prompt, "\\u", username);
    prompt = str_replace(prompt, "\\h", hostname);
    prompt = str_replace(prompt, "\\w", work_dir);
}

void run_command(node_t *node) {
    if (prompt)
        handle_prompt(getenv("PS1")); // in the end!!!!

    switch(node->type) {

    case NODE_COMMAND:
        handle_cmd(node);
        break;

    case NODE_PIPE:
        handle_pipe(node);
        break;

    case NODE_REDIRECT:
        handle_redirect(node);
        break;

    case NODE_SUBSHELL:
        ;
        subprocess_t sp = subprocess(node->subshell.child);
        close(sp.providefd);
        waitpid(sp.pid, NULL, 0);
        break;

    case NODE_DETACH:
        ;
        subprocess_t sp_d = subprocess(node->subshell.child);
        close(sp_d.providefd);
        waitpid(sp_d.pid, NULL, WNOHANG);
        break;

    case NODE_SEQUENCE:
        handle_seq(node);
        break;
    }
    if (prompt)
        handle_prompt(getenv("PS1")); // in the end!!!!
}



void handle_sigint(int sig) {
    sig--;
    if (pid_g > 0) {
        kill(pid_g, SIGINT);
        pid_g = -1;
    } else
        return;
    printf("\b\b\nKeyboardInterrupt\n");
}

int stop_flag_g = 0;

void initialize(void) {
    /* This code will be called once at startup */
    signal(SIGINT, handle_sigint);

    if (prompt)
        handle_prompt(getenv("PS1"));
}