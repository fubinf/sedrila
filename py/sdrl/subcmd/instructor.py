import argparse
import os
import re
import subprocess as sp
import time

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.interactive as i
import sdrl.participant
import sdrl.repo as r

meaning = """Help instructors evaluate a student's submission of several finished tasks.
"""


def add_arguments(subparser):
    subparser.add_argument('repo_url', action=RepoUrlAction,
                           help="where to find student input")
    subparser.add_argument('--get', default="True", action=argparse.BooleanOptionalAction,
                           help="pull or clone student repo")
    subparser.add_argument('--check', default="True", action=argparse.BooleanOptionalAction,
                           help="perform actual checking via interactive mode or subshell")
    subparser.add_argument('--put', default="True", action=argparse.BooleanOptionalAction,
                           help="commit and push to student repo")
    subparser.add_argument('--interactive', action=argparse.BooleanOptionalAction,
                           help="open interactive terminal interface to approve or reject tasks")
    subparser.add_argument('--override', action='store_true',
                           help="allow overriding of previous faulty gradings")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    home_fallback = "."
    if os.environ.get(c.REPOS_HOME_VAR) is None:
        b.warning(f"Environment variable {c.REPOS_HOME_VAR} is not set. "
                  "Assume current directory as student workdirs directory")
        if pargs.repo_url and os.path.isfile(c.PARTICIPANT_FILE):
            b.warning("It looks like you are already inside a student dir. Assuming parent directory instead.")
            home_fallback = ".."
    home = os.environ.get(c.REPOS_HOME_VAR) or home_fallback
    checkout_success = checkout_student_repo(pargs.repo_url, home, pargs.get)
    if not pargs.put and not pargs.check or not checkout_success:
        os.chdir("..")
        return
    student = sdrl.participant.Student()
    course = sdrl.course.CourseSI(configdict=student.metadatadict, context=student.metadata_url)
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


def checkout_student_repo(repo_url, home, pull=True):
    """Pulls or clones student repo and changes into its directory."""
    inrepo = os.path.isdir(".git") and os.path.isfile("student.yaml")
    if inrepo:
        username = os.path.basename(os.getcwd())
    else:
        username = git.username_from_repo_url(repo_url)
        os.chdir(home)
    if os.path.exists(username) or inrepo:
        if not inrepo:
            os.chdir(username)
        b.info(f"**** pulling repo in existing directory '{os.getcwd()}'")
        if pull:
            if repo_url:
                existing = git.remote_url()
                if repo_url != existing:
                    print(repo_url)
                    print(existing)
                    b.error("user repo with other url already present. please resolve manually. aborting")
                    return False
            git.pull()
        else:
            b.warning("not pulling user repo, relying on existing state")
    else:
        if not pull:
            b.warning("attempted to grade non-existing user without pulling.")
            b.warning("ignore and clone regardless.")
        git.clone(repo_url, username)
        if os.path.exists(username):
            os.chdir(username)
        else:
            b.critical(f"directory '{username}' not found")
        b.info(f"**** cloned repo into new directory '{os.getcwd()}'")
    return True


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
        b.info(f"Will now call the command given in the {c.REPO_USER_CMD_VAR} environment variable or else")
        b.info(f"the command given in the SHELL environment variable or else '{c.REPO_USER_CMD_DEFAULT}'.")
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
