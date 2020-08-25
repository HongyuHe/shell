#ifndef SHELL_AST_H
#define SHELL_AST_H

#include <stddef.h>

enum node_type
{
    NODE_COMMAND,
    NODE_PIPE,
    NODE_REDIRECT,
    NODE_SUBSHELL,
    NODE_SEQUENCE,
    NODE_DETACH
};

enum redirect_type
{
    REDIRECT_DUP = 0, // >& : (fd2 < 0 || mode == 0) and child == null
    REDIRECT_INPUT,   // <
    REDIRECT_OUTPUT,  // >
    REDIRECT_APPEND   // >>
};

struct tree_node;
typedef struct tree_node node_t;

struct tree_node
{
    enum node_type type;

    union {
        struct {
            char *program;
            char **argv;
            size_t argc;
        } command;

        struct {
            node_t **parts; // array
            size_t n_parts;
        } pipe;

        struct {
            node_t *child;
            int fd; // >= 0 specific fd; -1 stdout+stderr
            enum redirect_type mode;
            union {
                int fd2;
                char *target;
            };
        } redirect;

        struct {
            node_t *child;
        } subshell;

        struct {
            node_t *child;
        } detach;

        struct {
            node_t *first;
            node_t *second;
        } sequence;
    };
};

/*
 * This function de-allocates a command tree.
 */
void free_tree(node_t *root);

/*
 * This function prints a command tree on the standard output using a
 * tree structure.
 */
void print_tree(node_t *root);

/*
 * This function prints a command tree on the standard output using
 * the input format.
 */
void print_tree_flat(node_t *root, int print_final_newline);

/* Node constructors */
node_t *make_detach(node_t *child);
node_t *make_simple(char *prog);
node_t *extend_simple(node_t *cmd, char *arg);
node_t *make_seq(node_t *left, node_t *right);
node_t *make_pipe(node_t *first, node_t *second);
node_t *extend_pipe(node_t *pipe, node_t *extra);
node_t *make_subshell(node_t *child);
node_t *make_redir(node_t *child, int fd, int mode, int fd2, char *target);

#endif
