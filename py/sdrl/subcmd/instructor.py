import argparse
import contextlib
import os
import re
import subprocess as sp
import time
import typing as tg

import blessed

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.interactive as i
import sdrl.participant
import sdrl.repo as r
import sdrl.webapp

meaning = """Help instructors evaluate students' submissions of several finished tasks.
"""


def add_arguments(subparser):
    subparser.add_argument('workdir', nargs='*',
                           help="where to find student input")
    subparser.add_argument('--op', default="", choices=OP_CMDS.keys(),
                           help="Perform one operation non-interactively")
    subparser.add_argument('--port', '-p', type=int, default=sdrl.webapp.DEFAULT_PORT,
                           help=f"webapp will listen on this port (default: {sdrl.webapp.DEFAULT_PORT})")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    pargs.workdir = [wd.rstrip("/") for wd in pargs.workdir]  # make names canonical
    # ----- prepare:
    try:
        for workdir in pargs.workdir:
            if not os.path.isdir(workdir):
                b.critical(f"directory '{workdir}' does not exist.")
        if pargs.op == "pull":
            context = pargs.workdir
        else:
            if not pargs.op:
                pull_some_repos(pargs.workdir)
            context = sdrl.participant.make_context(pargs, pargs.workdir, sdrl.participant.Student, 
                                                    with_submission=True, show_size=True)
    except KeyboardInterrupt:
        print("  Bye.")
        return  # quit
    # ----- execute:
    if pargs.op:
        OP_CMDS[pargs.op](context)  # execute one command via lookup table, with duck-typed arg
    else:
        run_command_loop(context)


def run_command_loop(context):
    term = blessed.Terminal()
    try:
        while True:
            print(MENU)
            with term.cbreak():
                cmdkey = term.inkey()
            mycmd = MENU_CMDS.get(cmdkey)
            if mycmd:
                mycmd(context)
            elif str(cmdkey) == "q":
                break
    except KeyboardInterrupt:
        pass  # just quit


def cmd_webapp(ctx: sdrl.participant.Context):
    b.info("----- Start webapp to accept/reject submissions")
    sdrl.webapp.run(ctx)


def cmd_edit(ctx: sdrl.participant.Context):
    b.info(f"----- Edit '{c.PARTICIPANT_FILE}' files")
    b.error("(not yet implemented)")
    ...


def cmd_push(ctx: sdrl.participant.Context):
    b.info("----- Commit and push student repos")
    yesses = b.yesses("Commit & Push '%s'?", ctx.students)
    for yes, workdir in zip(yesses, ctx.students):
        if yes:
            b.info(f"Committing and pushing '{workdir}/{c.SUBMISSION_FILE}'")
            with contextlib.chdir(workdir):
                git.commit(*[c.SUBMISSION_FILE], msg=f"{c.SUBMISSION_FILE} checked", signed=True)
                git.push()
        else:
            b.info(f"Not committing '{workdir}/{c.SUBMISSION_FILE}'.")


def pull_some_repos(workdirs: tg.Iterable[str]):
    b.info("----- Pull student repos")
    yesses = b.yesses("Pull '%s'?", workdirs, yes_if_1=True)
    for yes, workdir in zip(yesses, workdirs):
        if yes:
            b.info(f"pulling '{workdir}':")
            with contextlib.chdir(workdir):
                git.pull()
        else:
            b.info(f"Not pulling '{workdir}'.")


MENU = "\n>>> w:webapp e:edit u:push q:quit   "
MENU_CMDS = dict(w=cmd_webapp, e=cmd_edit, u=cmd_push)
OP_CMDS = dict(pull=pull_some_repos, webapp=cmd_webapp, edit=cmd_edit)


def _xxx_oldstuff(pargs):
    student = sdrl.participant.Student()
    course = sdrl.course.CourseSI(configdict=student.course_metadata, context=student.course_metadata_url)
    commits = git.commits_of_local_repo(reverse=True)
    r.compute_student_work_so_far(course, commits)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    opentasks = rewrite_submission_file(course, c.SUBMISSION_FILE)
    entries = [entry for entry in entries if allow_grading(course, opentasks, entry, pargs.override)]
    entries = sorted(entries, key=lambda e: e.taskpath)  # sort by chapter+taskgroup
    if not pargs.check:
        b.info("Don't run check, just prepare commit")
    elif not entries:
        b.info("No tasks to check found. Assuming check already done. Preparing commit.")
    elif pargs.interactive:
        rejections = i.grade_entries(entries, student.course_url, pargs.override)
        if rejections is None:
            b.info("Nothing selected, nothing to do")
            return
        b.spit_yaml(c.SUBMISSION_FILE, r.submission_file_entries(entries, rejections, pargs.override))
        subshell_exit_info(reminder=True)
    else:
        call_instructor_cmd(course, instructor_cmd(), pargs, iteration=0)
    if pargs.put:
        validate_submission_file(course, c.SUBMISSION_FILE)
        commit_and_push(c.SUBMISSION_FILE)
    os.chdir("..")


def allow_grading(course, opentasks, entry: r.ReportEntry, override: bool) -> bool:
    task = course.task(entry.taskname)
    if not override:
        requirements = {requirement: course.task(requirement) for requirement in task.requires
                        if course.task(requirement) is not None}  # ignore Taskgroups
        open_requirements = [k for k, v in requirements.items()
                             if not any(k == name for name in opentasks) and not v.is_accepted and v.remaining_attempts]
        if open_requirements:
            return False
    isallowed = (entry.taskname in opentasks) != override
    if override:
        return isallowed and (task.rejections or task.is_accepted)
    return (isallowed and (task.remaining_attempts > 0) and
            (not task.is_accepted or opentasks[entry.taskname].endswith(c.SUBMISSION_ACCEPT_MARK)))


def read_submission_file() -> dict[str, str]:
    return b.slurp_yaml(c.SUBMISSION_FILE)


def rewrite_submission_file(course: sdrl.course.Course, filename: str):
    """Checks status of entries and inserts different marks where needed."""
    entries = b.slurp_yaml(filename)
    rewrite_submission_entries(course, entries)
    b.spit_yaml(filename, entries)
    return {taskname: mark for taskname, mark in entries.items() if mark != c.SUBMISSION_NONTASK_MARK}


def rewrite_submission_entries(course: sdrl.course.Course, entries: b.StrAnyDict):
    """Checks status of entries and inserts different marks where needed."""
    for taskname, mark in entries.items():
        task = course.task(taskname)
        if task is None:
            entries[taskname] = c.SUBMISSION_NONTASK_MARK
        elif task.is_accepted:
            entries[taskname] = c.SUBMISSION_ACCEPT_MARK
        elif task.rejections > 0:
            entries[taskname] += f" (previously rejected {task.rejections}x)"


def subshell_exit_info(reminder: bool = False):
    if reminder and not(os.environ.get(c.SEDRILA_COMMAND_ENV)):
        return  # explicit call, no subshell. no need to provide that info
    if reminder:
        b.info("You are still inside a subshell command!")
    b.info("Exit that command (e.g. the shell) to trigger automatic commit+push")
    b.info(f"of the modified {c.SUBMISSION_FILE}.")


def call_instructor_cmd(course: sdrl.course.Course, cmd: str,  # noqa
                        pargs: argparse.Namespace = None, iteration: int = 0):
    """Calls user-set command as indicated by environment variables"""
    if iteration == 0:
        b.info(f"Will now call the command given in the SHELL environment variable or else '{c.REPO_USER_CMD_DEFAULT}'.")
        b.info(f"The resulting command in your case will be:\n  '{cmd}'")
        subshell_exit_info()
        b.info(f"Please change status of tasks in {c.SUBMISSION_FILE} to either {c.SUBMISSION_ACCEPT_MARK}\n"
               f"or {c.SUBMISSION_REJECT_MARK} accordingly.")
        b.info("You can also just run `sedrila` to get an interactive list.")
        b.info("Feel free to add remarks at the end of the accept/reject lines.")
    else:
        b.info(f"Calling '{cmd}' again. (You can Ctrl-C right after it.)")
    if pargs:
        os.environ[c.SEDRILA_COMMAND_ENV] = f"instructor {pargs.repo_url} --interactive --no-get --no-put"
    sp.run(cmd, shell=True)
    time.sleep(0.8)  # give user a chance to hit Ctrl-C
    if pargs:
        del os.environ[c.SEDRILA_COMMAND_ENV]


def instructor_cmd() -> str:
    return os.environ.get(c.REPO_USER_CMD_VAR) or os.environ.get('SHELL', c.REPO_USER_CMD_DEFAULT)


def validate_submission_file(course: sdrl.course.Course, filename: str) -> bool:
    """Check whether the submission file contains (and only contains) sensible entries."""
    entries = b.slurp_yaml(filename)
    has_accept = any((r.is_accepted(mark) for taskname, mark in entries.items()))
    has_reject = any((r.is_rejected(mark) for taskname, mark in entries.items()))
    allowable_marks = (f"(?:{c.SUBMISSION_OVERRIDE_PREFIX})?{c.SUBMISSION_ACCEPT_MARK}|"
                       f"(?:{c.SUBMISSION_OVERRIDE_PREFIX})?{c.SUBMISSION_REJECT_MARK}|{c.SUBMISSION_CHECK_MARK}")
    is_valid = True
    
    def error(msg: str) -> bool:
        b.error(msg)
        return False
    if not has_accept and not has_reject:
        is_valid = b.error(f"Invalid {filename}: has neither {c.SUBMISSION_ACCEPT_MARK} nor "
                           f"{c.SUBMISSION_REJECT_MARK} marks.")
    for taskname, mark in entries.items():
        if not course.task(taskname):
            is_valid = error(f"No such task exists: {taskname}")
        if not re.match(allowable_marks, mark):
            is_valid = error(f"Impossible mark: \"{taskname}: {mark}\"")
    return is_valid


def commit_and_push(filename: str):
    assert filename == c.SUBMISSION_FILE  # our only purpose here, the arg is for clarity
    git.commit(*[filename], msg=f"{c.SUBMISSION_FILE} checked", signed=True)
    git.push()


class RepoUrlAction(argparse.Action):  # allow repo_url to be optional without --
    def __init__(self, option_strings, dest, nargs=None, **kwargs):  # noqa
        kwargs['required'] = not(os.path.isfile(c.PARTICIPANT_FILE))
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
