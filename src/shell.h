#ifndef SHELL_H
#define SHELL_H

struct tree_node;

/*
 * Any value assigned to this will be displayed when asking the user for a
 * command. Do not assign any value to this if its value is NULL, as this
 * indicates the session is not interactive.
 */
extern char *prompt;

/*
 * Called once when the shell starts.
 */
void initialize(void);

/*
 * Called when a command has been read from the user.
 */
void run_command(struct tree_node *n);

/* ... */

#endif
