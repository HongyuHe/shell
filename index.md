# Shell

## Introduction

This a Unix shell similar to `sh`, `bash` and `zsh`.
This implementation is not based on (or exploit) another shell. For example, `system(3)`.

## Implementation Details

- This shell could run all simple commands.
- This shell supports the `cd` and `exit` following built-in command
- It runs sequences of 3 commands or more properly.
- It runs pipes of 2 simple commands properly.
- This shell can pass all `valgrind` checks, as well as `gcc -Wall -Wextra`.
- It will print an error message on the standard output when an API function fails.
- This shell can handle interrupts such as Ctrl+C from users properly, but regular commands will still be interrupted when the user enters Ctrl+C.
- This implementation runs pipes of **more than 2 parts** consisting of sequences or pipes of simple commands.
- This shell supports **redirections**, **detached commands** and executing commands in a **sub-shell**.
- It supports the `set` and `unset` built-ins for managing environment variables.
- It can parse the PS1 correctly and support hostname, user name and current path. ( see `PROMPTING` in the `bash(1)` manual page)
- This shell supports simple **job control**: Ctrl+Z to suspend a command group, `bg` to continue a job in the background, and `fg` to recall a job to the foreground.

## Example commands

```sh
## simple commands:
ls
sleep 5   # must not show the prompt too early
```

```sh
## simple commands, with built-ins:
mkdir t
cd t
/bin/pwd  # must show the new path
exit 42   # terminate with code
```

```sh
## sequences:
echo hello; echo world # must print in this order
exit 0; echo fail  # must not print "fail"
```

```sh
## pipes:
ls | grep t
ls | more    # must not show prompt too early
ls | sleep 5 # must not print anything, then wait
sleep 5 | ls # must show listing then wait
ls /usr/lib | grep net | cut -d. -f1 | sort -u
```

```sh
## redirects:
>dl1 ls /bin; <dl1 wc -l
>dl2 ls /usr/bin; >>dl1 cat dl2 # append
<dl2 wc -l; <dl1 wc -l # show the sum
>dl3 2>&1 find /var/. # errors redirected
```

```sh
## detached commands:
sleep 5 &  # print prompt early
{ sleep 1; echo hello }& echo world; sleep 3 # invert output
```

```sh
## sub-shell:
( exit 0 ) # top shell does *not* terminate
cd /tmp; /bin/pwd; ( cd /bin ); /bin/pwd # "/tmp" twice
```

```sh
## environment variables
set hello=world; env | grep hello # prints "hello=world"
(set top=down); env | grep top # does not print "top=down"

# custom PATH handling
mkdir /tmp/hai; touch /tmp/hai/waa; chmod +x /tmp/hai/waa
set PATH=/tmp/hai; waa # OK
unset PATH; waa # execvp() reports failure
```

## Syntax of built-ins

Built-in: `cd <path>`
:   Change the current directory to become the directory specify in the argument. Your shell does not need to support the syntax `cd` without arguments like Bash does.

Built-in: `exit <code>`
:   Terminate the current shell process using the specified numeric code. Your shell does not need to support the syntax `exit` without arguments like Bash does.

Built-in (advanced): `set <var>=<value>`
:   Set the specified environment variable. Your shell does not need to support the syntax `set` without arguments like Bash does.

Built-in (advanced): `unset <var>` (optional)
:   Unset the specified environment variable.


## Error handling

This shell might encounter two types of error:

-   When an API function called by the shell fails, for example `execvp(2)` fails to find an executable program For these errors, this shell will print a usefu error message on its standard error. The helpe function `perror(3)` is used for this purpose.
-   When a command launched by the shell exits with a non-zero status code, or a built-in command encounters an error. For these errors, this shell will print a useful indicative message but this will not be tested.

## Notes

1. A shell usually supports redirections on all places of a simple command; `ls > foo` and `>foo ls` are normally equivalent. However, this shell only supports `>foo ls`.
2.  Within a 'pipe' construction, all parts should be forked, even if they only contain built-in commands. This keeps the implementation easier.

> ``` sh
> exit 42 # closes the shell
> exit 42 | sleep 1  # exit in sub-shell, main shell remains
>
> cd /tmp # changes the directory
> cd /tmp | sleep 1  # change directory in sub-shell
>                    # main shell does not
> ```

## Execution

1. install dependencies on Ubuntu using the following command:

    ```sh
    sudo apt install build-essential python python-pexpect libreadline-dev flex valgrind
    ```
2. Use `make check` to run tests.
