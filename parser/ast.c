#include "ast.h"
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#include <ctype.h>

node_t *make_redir(node_t *child, int fd, int mode, int fd2, char *target)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_REDIRECT;
    n->redirect.child = child;
    n->redirect.fd = fd;
    n->redirect.mode = mode;
    if (n->redirect.mode > 0) {
        assert(target != NULL);
        n->redirect.target = target;
    } else {
        n->redirect.fd2 = fd2;
    }
    return n;
}

node_t *make_simple(char *prog)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_COMMAND;
    n->command.program = prog;
    n->command.argv = malloc(2 * sizeof(char *));
    n->command.argv[0] = strdup(prog);
    n->command.argv[1] = NULL;
    n->command.argc = 1;
    return n;
}

node_t *extend_simple(node_t *cmd, char *extra)
{
    assert(cmd->type == NODE_COMMAND);
    cmd->command.argv = realloc(cmd->command.argv,
                                 sizeof(char *) * (cmd->command.argc + 2));
    cmd->command.argv[cmd->command.argc] = extra;
    cmd->command.argv[cmd->command.argc + 1] = NULL;
    cmd->command.argc++;
    return cmd;
}

node_t *make_pipe(node_t *first, node_t *second)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_PIPE;
    n->pipe.n_parts = 2;
    n->pipe.parts = malloc(2 * sizeof(node_t *));
    n->pipe.parts[0] = first;
    n->pipe.parts[1] = second;
    return n;
}

node_t *extend_pipe(node_t *n, node_t *extra)
{
    assert(n->type == NODE_PIPE);
    n->pipe.parts = realloc(n->pipe.parts, sizeof(node_t *) * (n->pipe.n_parts + 1));
    n->pipe.parts[n->pipe.n_parts] = extra;
    n->pipe.n_parts++;
    return n;
}

node_t *make_subshell(node_t *child)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_SUBSHELL;
    n->subshell.child = child;
    return n;
}

node_t *make_detach(node_t *child)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_DETACH;
    n->detach.child = child;
    return n;
}

node_t *make_seq(node_t *left, node_t *right)
{
    node_t *n = malloc(sizeof(node_t));
    n->type = NODE_SEQUENCE;
    n->sequence.first = left;
    n->sequence.second = right;
    return n;
}


void print_string(char *s)
{
    char *p;
    int escape = 0;
    for (p = s; *p; ++p)
        if (!isalnum(*p) && strchr(":%./=+,@*?^_-", *p) == NULL) {
            escape = 1;
            break;
        }
    if (escape) {
        putchar('"');
        for (size_t i = 0; s[i]; ++i)
            if (s[i] == '\\' || s[i] == '"') {
                putchar('\\');
                putchar(s[i]);
            } else if (!isprint(s[i]))
                printf("\\x%02x", s[i]);
            else
                putchar(s[i]);
        putchar('"');
    } else
        printf("%s", s);
}

void print_tree_flat(node_t *n, int nl)
{
    size_t i;

    if (!n) {
        printf("<NULL>");
        if (nl) putchar('\n');
        return;
    }

    switch(n->type) {
    case NODE_COMMAND:
        for (i = 0; i < n->command.argc; ++i) {
            if (i > 0)
                putchar(' ');
            print_string(n->command.argv[i]);
        }
        break;

    case NODE_PIPE:
        for (i = 0; i < n->pipe.n_parts; ++i) {
            if (i > 0)
                printf(" | ");
            printf(" { ");
            print_tree_flat(n->pipe.parts[i], 0);
            printf(" } ");
        }
        break;

    case NODE_REDIRECT:
        if (n->redirect.fd < 0)
            printf(" &");
        else
            printf(" %d", n->redirect.fd);

        switch(n->redirect.mode) {
        case 0: printf(">&%d", n->redirect.fd2); break;
        case 1: printf("<");  print_string(n->redirect.target); break;
        case 2: printf(">");  print_string(n->redirect.target); break;
        case 3: printf(">>"); print_string(n->redirect.target); break;
        }

        printf(" { ");
        print_tree_flat(n->redirect.child, 0);
        printf(" } ");
        break;

    case NODE_SUBSHELL:
        printf("( ");
        print_tree_flat(n->subshell.child, 0);
        printf(" )");
        break;

    case NODE_DETACH:
        printf(" { ");
        print_tree_flat(n->detach.child, 0);
        printf(" } &");
        break;

    case NODE_SEQUENCE:
        printf(" { ");
        print_tree_flat(n->sequence.first, 0);
        printf(" }; { ");
        print_tree_flat(n->sequence.second, 0);
        printf(" } ");
        break;
    }

    if (nl)
        putchar('\n');
}


static void print_ind(int ind)
{
    int i;
    for (i = 0; i < ind; ++i)
        printf("   ");
}

static void print_tree_rec(node_t *n, int ind)
{
    size_t i;

    print_ind(ind);
    if (!n) {
        printf("<NULL>\n");
        return;
    }

    switch(n->type) {
    case NODE_COMMAND:
        printf("COMMAND\n");
        print_ind(ind + 1);
        for (i = 0; i < n->command.argc; ++i) {
            if (i > 0)
                putchar(' ');
            print_string(n->command.argv[i]);
        }
        putchar('\n');
        break;

    case NODE_PIPE:
        printf("PIPE\n");
        for (i = 0; i < n->pipe.n_parts; ++i)
            print_tree_rec(n->pipe.parts[i], ind + 1);
        break;

    case NODE_REDIRECT:
        printf("REDIRECT\n");
        print_ind(ind + 1);
        if (n->redirect.fd < 0)
            printf("&");
        else
            printf("%d", n->redirect.fd);

        switch(n->redirect.mode)
        {
        case REDIRECT_DUP:    printf(">&%d", n->redirect.fd2); break;
        case REDIRECT_INPUT:  printf("<"); print_string(n->redirect.target); break;
        case REDIRECT_OUTPUT: printf(">"); print_string(n->redirect.target); break;
        case REDIRECT_APPEND: printf(">>"); print_string(n->redirect.target); break;
        }
        putchar('\n');
        print_tree_rec(n->redirect.child, ind + 1);
        break;

    case NODE_SUBSHELL:
        printf("SUBSHELL\n");
        print_tree_rec(n->subshell.child, ind + 1);
        break;

    case NODE_DETACH:
        printf("DETACH\n");
        print_tree_rec(n->detach.child, ind + 1);
        break;

    case NODE_SEQUENCE:
        printf("SEQUENCE\n");
        print_tree_rec(n->sequence.first, ind + 1);
        print_tree_rec(n->sequence.second, ind + 1);
        break;
    }
}


void print_tree(node_t *node)
{
    print_tree_rec(node, 0);
}

void free_tree(node_t *n)
{
    size_t i;

    if (!n)
        return;

    switch(n->type) {
    case NODE_COMMAND:
        free(n->command.program);
        for (i = 0; i < n->command.argc; ++i)
            free(n->command.argv[i]);
        free(n->command.argv);
        break;

    case NODE_PIPE:
        for (i = 0; i < n->pipe.n_parts; ++i)
            free_tree(n->pipe.parts[i]);
        free(n->pipe.parts);
        break;

    case NODE_REDIRECT:
        if (n->redirect.mode > 0)
            free(n->redirect.target);
        free_tree(n->redirect.child);
        break;

    case NODE_SUBSHELL:
        free_tree(n->subshell.child);
        break;

    case NODE_DETACH:
        free_tree(n->detach.child);
        break;

    case NODE_SEQUENCE:
        free_tree(n->sequence.first);
        free_tree(n->sequence.second);
        break;
    }
    free(n);
}
