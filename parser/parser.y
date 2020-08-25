%token_type { struct lex_token }
%token_destructor { if ($$.text) free($$.text); }
%default_type { node_t * }
%default_destructor { free_tree($$); }
%type commands { int }

%syntax_error { fprintf(stderr, "mysh: syntax error\n"); parse_error = 1; }

%left SEMI.
%left PIPE.

%include {
#include "../src/shell.h"
#include "ast.h"
#include "lexer.h"
#include <assert.h>
#include <stdlib.h>
int echo = 0;
int parse_error = 0;
#pragma GCC diagnostic ignored "-Wunused-parameter"
}

top ::= END. { }
top ::= seq(A) END. { if (parse_error) free_tree(A);
                      else { if (echo) print_tree_flat(A, 1);
                             run_command(A);
                             free_tree(A);
                           } }

seq(C) ::= pipe(A).             { C = A; }
seq(C) ::= pipe(A) SEMI.        { C = A; }
seq(C) ::= pipe(A) AMP.         { C = make_detach(A); }
seq(C) ::= pipe(A) SEMI seq(B). { C = make_seq(A, B); }
seq(C) ::= pipe(A) AMP seq(B).  { C = make_seq(make_detach(A), B); }

pipe(B) ::= redir(A).                { B = A; }
pipe(B) ::= pipe1(A).                { B = A; }
pipe1(C) ::= redir(A) PIPE redir(B). { C = make_pipe(A, B); }
pipe1(C) ::= pipe1(A) PIPE redir(B). { C = extend_pipe(A, B); }

redir(C) ::= group(A).                               { C = A; }
redir(C) ::=           GT    AMP NUMBER(B) redir(A). { C = make_redir(A, 1, 0, B.number, 0); free(B.text); }
redir(C) ::=           GT    WORD(B) redir(A).       { C = make_redir(A, 1, 2, 0, B.text); }
redir(C) ::=           GT GT WORD(B) redir(A).       { C = make_redir(A, 1, 3, 0, B.text); }
redir(C) ::=           LT    WORD(B) redir(A).       { C = make_redir(A, 0, 1, 0, B.text); }
redir(C) ::= AMP       GT    AMP NUMBER(B) redir(A). { C = make_redir(A, -1, 0, B.number, 0); free(B.text); }
redir(C) ::= AMP       GT    WORD(B) redir(A).       { C = make_redir(A, -1, 2, 0, B.text); }
redir(C) ::= NUMBER(D) GT    AMP NUMBER(B) redir(A). { C = make_redir(A, D.number, 0, B.number, 0); free(B.text); free(D.text); }
redir(C) ::= NUMBER(D) GT    WORD(B) redir(A).       { C = make_redir(A, D.number, 2, 0, B.text); free(D.text); }
redir(C) ::= NUMBER(D) GT GT WORD(B) redir(A).       { C = make_redir(A, D.number, 3, 0, B.text); free(D.text); }
redir(C) ::= NUMBER(D) LT    WORD(B) redir(A).       { C = make_redir(A, D.number, 1, 0, B.text); free(D.text); }

group(B) ::= simple(A).         { B = A; }
group(B) ::= BRL seq(A) BRR. { B = A; }
group(B) ::= PL seq(A) PR.   { B = make_subshell(A); }

simple(B) ::= WORD(A).             { B = make_simple(A.text); }
simple(B) ::= NUMBER(A).           { B = make_simple(A.text); }
simple(C) ::= simple(A) WORD(B).   { C = extend_simple(A, B.text); }
simple(C) ::= simple(A) NUMBER(B). { C = extend_simple(A, B.text); }
