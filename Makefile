# ADDITIONAL_SOURCES =

# ADDITIONAL_HEADERS =

TARGET = mysh
SOURCES = src/front.c src/shell.c parser/ast.c $(ADDITIONAL_SOURCES)
HEADERS = parser/lexer.h parser/ast.h src/shell.h $(ADDITIONAL_HEADERS)
GENERATED_SOURCES = parser/parser.c parser/lex.yy.c
GENERATED_HEADERS = parser/parser.h parser/lex.yy.h
META_SOURCES = parser/parser.y parser/lexer.l parser/lemon.c parser/lempar.c
META = Makefile check.py

CFLAGS = -Wall -Wextra -std=gnu99 -g3
LDFLAGS =
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
LIBS = -lreadline
else
LIBS = -lreadline -lhistory
endif

CC = gcc
LEX = flex
LEMON = parser/lemon

.PHONY: all tarball clean moreclean

all: $(TARGET)

tarball: shell.tar.gz

shell.tar.gz: $(SOURCES) $(HEADERS) $(META_SOURCES) $(META)
	tar -czf $@ $^

check:
	@./check.py

clean:
	rm -f $(TARGET)
	rm -f *.tar.gz
	rm -f **/*.o **/*.out
	rm -f *.aux *.log *.ltx *~
	rm -f _valgrind.out a b mysh

moreclean: clean
	rm -f $(GENERATED_SOURCES) $(GENERATED_HEADERS)
	rm -f $(LEMON)

$(TARGET): $(SOURCES:.c=.o) $(GENERATED_SOURCES:.c=.o)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)

$(SOURCES:.c=.o): $(HEADERS) $(GENERATED_HEADERS)

$(LEMON): parser/lemon.c
	$(CC) $(CFLAGS) -o $@ $<

parser/parser.h: parser/parser.c
parser/parser.c: parser/parser.y $(LEMON)
	$(LEMON) $<

parser/lex.yy.h parser/lex.yy.c: parser/lexer.l
	$(LEX) --header-file=parser/lex.yy.h -o parser/lex.yy.c $<
