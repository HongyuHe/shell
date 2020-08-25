#ifndef SHELL_LEXER_H
#define SHELL_LEXER_H

#include <stddef.h>

struct lex_token {
    char *text;
    int number;
};
extern char *token_text;

void *ParseAlloc(void * (*)(size_t));
void ParseFree(void *, void (*)(void *));
void Parse(void *, int, struct lex_token);

#endif
