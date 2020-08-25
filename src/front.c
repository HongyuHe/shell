#include "../parser/parser.h"
#include "../parser/lexer.h"
#include "../parser/lex.yy.h"
#include "shell.h"
#include <stdio.h>
#include <unistd.h>
#include <getopt.h>
#include <errno.h>
#include <string.h>
#include <readline/readline.h>
#include <readline/history.h>

char *prompt = NULL;
extern int echo, parse_error; /* From the parser */

static void handle_command(char *cmd) {
    void *parser;
    int yv;
    struct lex_token tok;
    YY_BUFFER_STATE st;

    /* Prepare a parser context */
    parser = ParseAlloc(malloc);
    parse_error = 0;

    /* Prepare a lexer context */
    st = yy_scan_string(cmd);

    /* While there are some lexing tokens... */
    while ((yv = yylex()) != 0) {
        tok.text = NULL;
        tok.number = -1;

        /* NUMBER and WORD are the only 2 token types with a carried value. */
        if (yv == NUMBER || yv == WORD) {
            tok.text = strdup(token_text);
            if (yv == NUMBER)
                tok.number = atoi(tok.text);
        }

        /* Process the token in the parser. */
        Parse(parser, yv, tok);

        /* If at end, finish the parsing. */
        if (yv == END)
            break;
    }

    /* Complete parse */
    Parse(parser, 0, tok);

    ParseFree(parser, free);
    yy_delete_buffer(st);
}

void my_yylex_destroy(void) {
    yylex_destroy();
}

int main(int argc, char *argv[]) {
    int save_history = 0;
    char *line;
    int opt;

    /* Command-line argument parsing */
    while ((opt = getopt(argc, argv, "hec:")) != -1) {
        switch(opt) {
        case 'h':
            printf("usage: %s [OPTS] [FILE]\n"
                   "options:\n"
                   " -h      print this help.\n"
                   " -e      echo commands before running them.\n"
                   " -c CMD  run this command then exit.\n"
                   " FILE    read commands from FILE.\n",
                   argv[0]);
            return EXIT_SUCCESS;

        case 'e':
            echo = 1;
            break;

        case 'c':
            initialize();
            handle_command(optarg);
            return 0;
        }
    }

    /* Reading commands from either a script or stdin */
    if (optind >= argc) {
        /* Reading from stdin; handle history if terminal. */
        if (isatty(0)) {
            using_history();
            read_history(0);
            prompt = "mysh$ ";
            save_history = 1;
        }
    } else {
        /* Reading from file. */
        FILE *f = fopen(argv[optind], "r");
        if (!f) {
            perror(argv[optind]);
            exit(1);
        }
        rl_instream = f;
        prompt = NULL;
    }

    /* The main loop. */
    initialize();
    while ((line = readline(prompt))) {
        if (save_history && line[0] != '\0') {
            add_history(line);
            write_history(NULL);
        }
        handle_command(line);
        free(line);
    }

    return 0;
}
