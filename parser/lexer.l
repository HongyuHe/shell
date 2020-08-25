%{
#include "parser.h"
#include "lexer.h"
#include <stdio.h>
#include <stdlib.h>
#include <readline/history.h>
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wsign-compare"

char *token_text = 0;
char *string_buf = 0;
size_t string_buf_len = 0;
char *string_buf_ptr = 0;
static void reset_text(void);
static void extend_text(char *);
static void extend_text1(int);
static void extend_textx(char *);
static void free_text(void);

%}

SIMPLECHAR [a-zA-Z0-9:%./=+,@*?^_\-]
NSIMPLECHARQ [^a-zA-Z0-9:%./=+,@*?^_\\\-\"]

%x text str

%%

[ \t]+                  { /*whitespace*/ }

"#"[^\n]+               { /*comment*/ }

"<"                     { return LT; }
">"                     { return GT; }
"&"                     { return AMP; }
";"                     { return SEMI; }
"|"                     { return PIPE; }
"{"                     { return BRL; }
"}"                     { return BRR; }
"("                     { return PL; }
")"                     { return PR; }

<INITIAL><<EOF>>        { return END; }

[0-9]+                  { token_text = yytext; return NUMBER; }

{SIMPLECHAR}+           { reset_text(); extend_text (yytext);    BEGIN(text); }
\\x[0-9a-fA-F]{2}       { reset_text(); extend_textx(yytext+2);  BEGIN(text); }
\\.                     { reset_text(); extend_text1(yytext[1]); BEGIN(text); }
\"                      { reset_text(); BEGIN(str); }

<text>{SIMPLECHAR}+     { extend_text (yytext); }
<text>\\x[0-9a-fA-F]{2} { extend_textx(yytext + 2); }
<text>\\.               { extend_text1(yytext[1]); }
<text>\"                { BEGIN(str); }
<text>""/{NSIMPLECHARQ} { extend_text1(0); BEGIN(INITIAL); token_text = string_buf; return WORD; }
<text><<EOF>>           { extend_text1(0); BEGIN(INITIAL); token_text = string_buf; return WORD; }

<str>\"                 { BEGIN(text); }
<str>\\x[0-9a-fA-F]{2}  { extend_textx(yytext + 2); }
<str>\\n                { extend_text1('\n'); }
<str>\\t                { extend_text1('\t'); }
<str>\\r                { extend_text1('\r'); }
<str>\\b                { extend_text1('\b'); }
<str>\\f                { extend_text1('\f'); }
<str>\\.                { extend_text1(yytext[1]); }
<str>[^\\\n\"]+         { extend_text (yytext); }
<str><<EOF>>            { fprintf(stderr, "mysh: unterminated quoted string\n");
                          BEGIN(INITIAL); yyterminate(); }

.                       { yyterminate(); }

%%


static void reset_text(void)
{
    if (string_buf_len == 0)
    {
        string_buf = malloc(32);
        string_buf_len = 32;
        atexit(free_text);
    }
    string_buf_ptr = string_buf;
}

static void extend_text1(int c)
{
    size_t l = string_buf_ptr - string_buf;
    if (l >= string_buf_len)
    {
        string_buf_len *= 2;
        string_buf = realloc(string_buf, string_buf_len);
    }
    string_buf_ptr = string_buf + l;
    *string_buf_ptr++ = c;
}

static void extend_text(char *s)
{
    while (*s)
        extend_text1(*s++);
}

static void extend_textx(char *s)
{
    int c;
    (void)sscanf(s, "%x", &c);
    extend_text1(c);
}

static void free_text(void)
{
    free(string_buf);
}

int yywrap(void)
{
   return 1;
}
