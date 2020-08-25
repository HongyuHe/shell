#!/usr/bin/env python2
from __future__ import print_function

import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import pexpect

STUDENT_SHELL = "./mysh"

# Only used on server, to ensure an unchanged Makefile
CLEAN_MAKEFILE = "/framework/Makefile"


# Some global state - set by one (or more) test and used later to subtract
# points
valgrind_failed = None
valgrind_output = None
compiler_warnings = None

# Set per-testcase and used by the function actually running the test XXX nasty
run_with_valgrind = True

# Set by every run_cmd so the signal handler knows where it failed.
last_command = ""

# C files added by student - we need these during compilation
additional_sources = ""


class TestError(Exception):
    pass


# Helper functions for performing common tests
def eq(a, b, name="Objects"):
    if a != b:
        if isinstance(a, str) and a.count('\n') > 3:
            raise TestError("%s not equal: \"%s\" and \"%s\"" % (name, a, b))
        else:
            raise TestError("%s not equal: %s and %s" % (name, repr(a),
                repr(b)))


def colored(val, color=None, bold=False, underline=False, blink=False,
        hilight=False):
    C_RESET = '\033[0m'
    C_BOLD = '\033[1m'
    C_UNDERLINE = '\033[4m'
    C_BLINK = '\033[5m'
    C_HILIGHT = '\033[7m'
    C_GRAY = '\033[90m'
    C_RED = '\033[91m'
    C_GREEN = '\033[92m'
    C_YELLOW = '\033[93m'
    C_BLUE = '\033[94m'
    C_PINK = '\033[95m'
    C_CYAN = '\033[96m'

    codes = ''
    if bold: codes += C_BOLD
    if underline: codes += C_UNDERLINE
    if blink: codes += C_BLINK
    if hilight: codes += C_HILIGHT
    if color:
        codes += {'gray': C_GRAY,
                  'red': C_RED,
                  'green': C_GREEN,
                  'yellow': C_YELLOW,
                  'blue': C_BLUE,
                  'pink': C_PINK,
                  'cyan': C_CYAN}[color]

    return '%s%s%s' % (codes, val, C_RESET)

# Test case definition
class Test():
    def __init__(self, name, func, valgrind=False):
        self.name, self.func, self.valgrind = name, func, valgrind


# Collection of testcases worth n points (i.e. one item in the grading scheme)
class TestGroup():
    def __init__(self, name, points, *tests, **kwargs):
        self.name = name
        self.points = float(points)
        self.tests = tests
        self.stop_if_fail = kwargs.get("stop_if_fail", False)

    def run(self):
        succeeded = 0
        for test in self.tests:
            global run_with_valgrind
            run_with_valgrind = test.valgrind
            print('\t' + test.name, end=': ')
            try:
                test.func()
            except TestError as e:
                print(colored("FAIL", color='red'))
                print(e.args[0])
                if self.stop_if_fail:
                    break
            else:
                print(colored("OK", color='green'))
                succeeded += 1
        return succeeded


def test_groups(groups, writer=None, force_fail=False):
    points = 0.0
    for group in groups:
        if force_fail:
            if writer: writer.write(group.name + ": 0\n")
            continue

        print(colored(group.name, color='blue', bold=True))
        succeeded = group.run()

        perc = ((1. * succeeded) / len(group.tests))
        if group.points < 0:
            perc = 1 - perc
        grouppoints = round(group.points * perc, 2)
        if group.points > 0:
            print(" Passed %d/%d tests, %.2f/%.2f points" % (succeeded,
                len(group.tests), grouppoints, group.points))
        else:
            if perc > 0:
                print(" Failed, subtracting %.2f points" % abs(grouppoints))
        if writer: writer.write(group.name + ": " + str(grouppoints) + "\n")
        points += grouppoints
        if group.stop_if_fail and succeeded != len(group.tests):
            force_fail = True
    return points


def run(writer=None):
    basic_tests = [
        TestGroup("Valid submission", 1.0,
            Test("Make", check_compile),
            stop_if_fail=True),
        TestGroup("Simple commands", 1.0,
            Test("Simple", bash_cmp("pwd"), valgrind=False),
            Test("Arguments", bash_cmp("ls -alh /bin")),
            Test("Wait for 1 proc", test_wait("sleep 2", 2)),
            stop_if_fail=True),
        TestGroup("exit builtin", 1.0,
            Test("exit", test_exit),
        ),
        TestGroup("cd builtin", 1.0,
            Test("cd", test_cd),
        ),
        TestGroup("Sequences", 1.5,
            Test("Simple sequence", bash_cmp("pwd; uname"), valgrind=False),
            Test("Nested sequences", bash_cmp("pwd; cd /; pwd")),
            Test("Wait for sequence", test_wait("sleep 1; sleep 2", 3.0)),
        ),
        TestGroup("Pipes", 1.5,
            Test("One pipe", bash_cmp("ls -alh / | grep lib"), valgrind=False),
            Test("cd in pipe", bash_cmp("cd / | pwd")),
            Test("exit in pipe", bash_cmp("exit 1 | pwd")),
            Test("Wait for pipes 1", test_wait("sleep 2 | sleep 1", 2.0)),
            Test("Wait for pipes 2", test_wait("sleep 1 | sleep 2", 2.0)),
        ),
        TestGroup("Valgrind memcheck", -1,
            Test("No errors", check_valgrind),
        ),
        TestGroup("Compiler warnings", -1,
            Test("No warnings", check_warnings),
        ),
        TestGroup("Errors", -1.0,
            Test("Binary not in path", test_errors),
        ),
        TestGroup("Signals", -1.0,
            Test("Ctrl-c", test_ctrl_c),
        ),
    ]

    advanced_tests = [
        TestGroup("Pipes >2p with seqs or pipes", 1.0,
            Test("Multiple pipes",
                bash_cmp("ls -alh / | grep lib | grep -v 32 | tac")),
            Test("Seq in pipe",
                bash_cmp("ls | { grep c ; ls /bin ; } | tac")),
            Test("Seq wait 1",
                test_wait("{ sleep 1 | sleep 2; }; exit 1", 2)),
            Test("Seq wait 2",
                test_wait("{ sleep 2 | sleep 1; }; exit 1", 2)),
            Test("Seq wait 3",
                test_wait("{ sleep 2 | sleep 3 | sleep 1; }; exit 1", 3)),
        ),
        TestGroup("Redirections", 1.0,
            Test("To/from file", bash_cmp(">a ls /bin; <a wc -l")),
            Test("Overwrite", bash_cmp(">a ls /bin; >a ls; cat a")),
            Test("Append", bash_cmp(">a ls; >>a pwd; cat a")),
            Test("Errors", bash_cmp(">a 2>&1 du /etc/.", check_rv=False)),
            Test("Errors to out", bash_cmp("2>&1 >/dev/null find /etc/.",
                check_rv=False)),
        ),
        TestGroup("Detached commands", 0.5,
            Test("sleep", test_detach),
            Test("Sequence",
                bash_cmp("{ sleep 0.1; echo hello; }& echo world; sleep 0.3")),
        ),
        TestGroup("Subshells", 0.5,
            Test("exit", bash_cmp("(pwd; exit 2); exit 1")),
            Test("cd", bash_cmp("cd /bin; pwd; (cd /; pwd); pwd")),
        ),
        TestGroup("Environment variables", 0.5,
            Test("Simple", manual_cmp("set hello=world; env | grep hello",
                out="hello=world\n", err="")),
            Test("Subshell",
                manual_cmp("set hello=world; (set hello=bye); env | grep hello",
                out="hello=world\n", err="")),
            Test("Unset", manual_cmp("set hoi=daar; env | grep ^hoi; " +
                                     "unset hoi; env | grep ^hoi",
                                     out="hoi=daar\n", err="", rv=0)),
        ),
        TestGroup("Prompt", 0.5,
            Test("Username", test_prompt("u=\u $")),
            Test("Hostname", test_prompt("h=\h $")),
            Test("Working dir", test_prompt("w=\w $")),
            Test("Combined", test_prompt("u=\u h=\h w=\w $")),
        ),
        TestGroup("Job control", 2.0,
            Test("Ctrl-z", test_ctrl_z),
            Test("Ctrl-z + bg + fg", test_bg_fg),
            Test("Detach + fg", test_detach_fg),
            Test("Detach + fg + Ctrl-z + bg + fg", test_advanced_jobs),
        ),
        ]
    # Test arbitraly setion: 
    # mytests = [
    #     TestGroup("Job control", 2.0,
    #         Test("Ctrl-z", test_ctrl_z),
    #         Test("Ctrl-z + bg + fg", test_bg_fg),
    #         Test("Detach + fg", test_detach_fg),
    #         Test("Detach + fg + Ctrl-z + bg + fg", test_advanced_jobs),
    #     ),
    # ]
    # points = test_groups(mytests, writer)
    # return
    points = test_groups(basic_tests, writer)
    totalpoints = sum([g.points for g in basic_tests if g.points > 0])

    if points >= 5.0:
        print("Passed basic tests with enough points, doing advanced tests")
        points += test_groups(advanced_tests, writer)
        totalpoints += sum([g.points for g in advanced_tests if g.points > 0])
    else:
        #test_groups(advanced_tests, writer, force_fail=True)
        print("Didnt get enough points for the basic tests, aborting.")
        print("Got %.2f points, need at least 5.0" % points)

    print()
    print("Executed all tests, got %.2f/%.2f points in total" % (points,
        totalpoints))


def run_cmd(cmd, shell=None, prefix=None):
    global last_command
    last_command = cmd
    shell = shell or STUDENT_SHELL
    prefix = prefix or []
    return subprocess.Popen(
        prefix + [shell, "-c", cmd],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)


def run_mysh(cmd):
    global valgrind_failed, valgrind_output
    if not run_with_valgrind or valgrind_failed is not None:
        proc = run_cmd(cmd)
        out, err = proc.communicate()
        return proc.returncode, out, err
    else:
        proc = run_cmd(cmd, prefix=["valgrind", "--log-file=_valgrind.out"])
        out, err = proc.communicate()

        with open("_valgrind.out") as f:
            o = f.read()
        for line in o.split("\n"):
            if 'ERROR SUMMARY' in line:
                nerrors = int(line.split()[3])
                if nerrors:
                    valgrind_failed = cmd
                    valgrind_output = o
                break

        return proc.returncode, out, err


def check_valgrind():
    if valgrind_failed is None:
        global run_with_valgrind
        run_with_valgrind = True
        run_mysh("pwd | (ls -alh /) | (pwd|pwd) | {pwd;pwd} | " +
                 "{{pwd|pwd};pwd} | 2>&1 >/dev/null ls . fdsfsa | >a pwd | " +
                 ">>b pwd | (pwd &) | cd / | exit 31")
    if valgrind_failed is not None:
        raise TestError("Valgrind failed for command %s:\n%s" %
                (valgrind_failed, valgrind_output))


def check_warnings():
    if compiler_warnings is not None:
        raise TestError("Got compiler warnings:\n%s" % compiler_warnings)


def check_compile():
    check_cmd("make moreclean ADDITIONAL_SOURCES=\"%s\"" %
              additional_sources)

    out, err = check_cmd("make ADDITIONAL_SOURCES=\"%s\"" %
                         additional_sources)
    err = '\n'.join([l for l in err.split("\n") if not l.startswith("make:")])
    if "warning" in err:
        global compiler_warnings
        compiler_warnings = err

    check_cmd("%s -h" % STUDENT_SHELL)


def check_cmd(cmd):
    args = shlex.split(cmd)
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate()

    if p.returncode:
        raise TestError("Command returned non-zero value.\n" +
                "Command: %s\nReturn code: %d\nstdout: %s\nstderr: %s" %
                (cmd, p.returncode, stdout, stderr))
    return stdout, stderr


def bash_cmp(cmd, check_rv=True):
    def bash_cmp_inner():
        rv, stdout1, stderr1 = run_mysh(cmd)
        p2 = run_cmd(cmd, shell="bash")
        stdout2, stderr2 = p2.communicate()

        try:
            eq(stdout1, stdout2, "stdout")
            eq(stderr1, stderr2, "stderr")
            if check_rv:
                eq(rv, p2.returncode, "return value")
        except TestError as e:
            raise TestError("Error while comparing your shell output to " +
                "bash.\nCommand: %s\n%s" % (cmd, e.args[0]))
    return bash_cmp_inner


def manual_cmp(cmd, out=None, err=None, rv=None):
    def manual_cmp_inner():
        rv1, stdout1, stderr1 = run_mysh(cmd)

        try:
            if out is not None:
                eq(stdout1, out, "stdout")
            if err is not None:
                eq(stderr1, err, "stderr")
            if rv is not None:
                eq(rv1, rv, "return value")
        except TestError as e:
            raise TestError("Error while comparing your shell output to " +
                "expected output.\nCommand: %s\n%s" % (cmd, e.args[0]))
    return manual_cmp_inner


def test_wait(cmd, timeout, out='', err='', offset=0.3):
    timeout = float(timeout)
    def wait():
        start_time = time.time()
        stdout, stderr = run_cmd(cmd).communicate()
        end_time = time.time()
        eq(stdout, out, "stdout")
        eq(stderr, err, "stderr")

        if not (timeout - offset < end_time - start_time < timeout + offset):
            raise TestError("Command did not finish in expected time.\n" +
                    "Command: %s\nExpected time: %f\nTime taken: %f" % (cmd,
                        timeout, end_time - start_time))
    return wait


def test_exit():
    global last_command
    last_command = "exit 42 ... make sure your shell prompt contains a '$'"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')
    p.sendline("exit 42")
    try:
        p.expect('\$')
    except pexpect.EOF:
        try:
            p.wait()
        except pexpect.ExceptionPexpect:
            pass
        eq(p.exitstatus, 42, "exit status")
        return

    raise TestError("Shell did not exit on 'exit' command.")

def test_prompt(prompt):
    def expected_prompt(cwd=None):
        import getpass, socket
        return prompt.replace("\u", getpass.getuser())\
                     .replace("\h", socket.gethostname())\
                     .replace("\w", cwd or os.getcwd())
    def test_prompt_inner():
        global last_command
        last_command = "<none>"

        p = pexpect.spawn(STUDENT_SHELL, env={"PS1": prompt})
        p.setwinsize(10, 1024) # Otherwise long prompts get truncated
        p.expect("\$")
        if p.before + "$" != expected_prompt():
            raise TestError("Prompt incorrect for \"%s\", expected \"%s\", got "
                    "\"%s\"" % (prompt, expected_prompt(), p.before + "$"))
        if "\w" in prompt:
            p.sendline("cd /")
            p.expect("\$")
            lines = p.before.split("\r\n")
            if lines[0] != "cd /":
                raise TestError("Expected \"cd /\", got \"%s\"" % lines[0])

            if lines[1] + "$" != expected_prompt("/"):
                raise TestError("Prompt incorrect for \"%s\", expected \"%s\", "
                        "got \"%s\"" % (prompt, expected_prompt("/"),
                                        lines[1] + "$"))

    return test_prompt_inner

def test_detach():
    global last_command
    last_command = "sleep 1 &"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')
    p.sendline("sleep 1 &")
    stime = time.time()
    p.expect('\$')
    if time.time() - stime > 0.1:
        raise TestError("Detach did not return immediately.\n" +
                        "Command: sleep 1 &")
    p.sendline("ps")
    stime = time.time()
    p.expect('\$')
    if time.time() - stime > 0.1:
        raise TestError("Command after detach did not return immediately.\n" +
                        "Command: sleep 1 & \\n ps")
    if "sleep" not in p.before:
        raise TestError("Detached command not in ps output.\n" +
                        "Command: sleep 1 &")


def test_cd():
    global last_command
    last_command = "cd /tmp; pwd"

    p = subprocess.Popen([STUDENT_SHELL], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate("cd /tmp\npwd\n")
    eq(stdout, "cd /tmp\npwd\n/tmp\n", "stdout")  # readline echo's input back
    eq(stderr, "", "stderr")


def sleep_status(p):
    p.sendline("ps t")
    p.expect('\$')

    for line in p.before.split('\n'):
        if 'sleep' in line:
            return line.split()[2]

    raise TestError("Sleep not found in background.")


def test_ctrl_z():
    global last_command
    last_command = "sleep 2"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')

    try:
        p.sendline("sleep 2")
        stime = time.time()
        p.send(chr(26))
        p.expect('\$')
        if time.time() - stime > 0.5:
            raise TestError("Sleep was not stopped by SIGTSTP in time "
                    "(%.2f sec) %s." % (time.time() - stime, p.before))

        if sleep_status(p) != 'T':
            raise TestError("Sleep found in background, but not stopped.")
    except pexpect.EOF:
        raise TestError("Shell exited due to SIGTSTP (ctrl-z)")
    p.close()


def test_bg_fg():
    global last_command
    last_command = "sleep 0.5"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')

    try:
        p.sendline("sleep 0.5")
        stime = time.time()
        p.send(chr(26))
        p.expect('\$')
        if time.time() - stime > 0.5:
            raise TestError("Sleep was not stopped by SIGTSTP in time.")
        stat = sleep_status(p)
        if stat == 'T+':
            raise TestError("Sleep correctly stopped in background, but still "
                            "in foreground process group. Are you using "
                            "setpgid() correctly?")
        if stat != 'T':
            raise TestError("Sleep found in background, but not stopped "
                            "('ps t' should show status 'T').")

        p.sendline("bg")
        p.expect('\$')
        if sleep_status(p) != 'S':
            raise TestError("Sleep did not continue in background after bg "
                            "command.")

        p.sendline("fg")
        p.expect('\$')
        if time.time() - stime < 0.45:
            raise TestError("Sleep did not finish properly with a wait after "
                            "fg.")
    except pexpect.EOF:
        raise TestError("Shell exited due to SIGTSTP (ctrl-z) or bg/fg")
    p.close()


def test_detach_fg():
    global last_command
    last_command = "sleep 0.5 &"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')

    p.sendline("sleep 0.5 &")
    stime = time.time()
    p.expect('\$')
    if sleep_status(p) != 'S':
        raise TestError("Sleep not running in background.")

    p.sendline("fg")
    p.expect('\$')
    if time.time() - stime < 0.45:
        raise TestError("Sleep did not finish properly with a wait after fg.")

    p.close()


def test_advanced_jobs():
    global last_command
    last_command = "sleep 1 &"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')

    p.sendline("sleep 1 &")
    stime = time.time()
    p.expect('\$')
    if sleep_status(p) != 'S':
        raise TestError("Sleep not running in background.")

    p.sendline("fg")
    p.send(chr(26))
    p.expect('\$')
    stat = sleep_status(p)
    if stat == 'T+':
        raise TestError("Sleep correctly stopped in background, but still in "
                        "foreground process group. Are you using setpgid() "
                        "correctly?")
    if stat != 'T':
        raise TestError("Sleep found in background, but not stopped ('ps t' "
                        "should show status 'T').")

    p.sendline("fg")
    p.expect('\$')
    if time.time() - stime < 0.95:
        raise TestError("Sleep did not finish properly with a wait after fg.")

    p.close()


def test_ctrl_c():
    global last_command
    last_command = "sleep 2"

    p = pexpect.spawn(STUDENT_SHELL)
    p.expect('\$')

    try:
        p.sendline("sleep 2")
        stime = time.time()
        p.send(chr(3))
        p.expect('\$')
        if time.time() - stime > 0.3:
            raise TestError("Sleep was not killed by SIGINT in time.")

        time.sleep(0.2)
        p.sendline("ps")
        p.expect('\$')
        if "sleep" in p.before:
            raise TestError("Sleep still active in background.")
    except pexpect.EOF:
        raise TestError("Shell exited due to SIGINT (ctrl-c)")
    p.close()


def test_errors():
    rv, stdout, stderr = run_mysh("blablabla")
    eq(stdout, "", "stdout")
    if "No such file or directory" not in stderr:
        raise TestError("String \"No such file or directory\" not found in " +
                        "stderr: use perror if execvp fails.")


def do_additional_params(lst, name, suffix=''):
    for f in lst:
        if not f.endswith(suffix):
            raise TestError("File does not end with %s in %s: '%s'" %
                    (suffix, name, f))
        if '"' in f:
            raise TestError("No quotes allowed in %s: '%s'" % (name, f))
        if '/' in f:
            raise TestError("No slashes allowed in %s: '%s'" % (name, f))
        if '$' in f:
            raise TestError("No $ allowed in %s: '%s'" % (name, f))
        if f.startswith('-'):
            raise TestError("No flags allowed in %s: '%s'" % (name, f))


def fix_makefiles():
    with open('Makefile', 'r') as f:
        addsrc, addhdr = [], []
        for l in f:
            l = l.strip()
            if l.startswith("ADDITIONAL_SOURCES = "):
                addsrc = filter(bool, l.split(' ')[2:])
            if l.startswith("ADDITIONAL_HEADERS = "):
                addhdr = filter(bool, l.split(' ')[2:])
    do_additional_params(addsrc, "ADDITIONAL_SOURCES", ".c")
    do_additional_params(addhdr, "ADDITIONAL_HEADERS", ".h")

    global additional_sources
    additional_sources = ' '.join(addsrc)

    # On the server we overwrite the submitted makefile with a clean one. For
    # local tests this will fail, which is fine.
    try:
        shutil.copyfile(CLEAN_MAKEFILE, 'Makefile')
    except IOError:
        pass


def handle_sigterm(signum, frame):
    raise Exception("SIGTERM while executing command:\n\"%s\"" % last_command)


if __name__ == '__main__':
    os.chdir(os.path.dirname(sys.argv[0]) or '.')
    signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        fix_makefiles()
        run(open(sys.argv[1], 'w') if len(sys.argv) > 1 else None)
    except Exception as e:
        print("\n\nTester got exception: %s" % str(e))
