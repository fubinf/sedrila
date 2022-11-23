import argparse
import os
import typing as tg

import yaml

import base as b
import git
import sdrl.course
import sdrl.repo as r

help = """Help instructors evaluate a student's submission of several finished tasks.
"""

REPOS_HOME_VAR = "SEDRILA_INSTRUCTOR_REPOS_HOME"
USER_CMD_VAR = "SEDRILA_INSTRUCTOR_COMMAND"
USER_CMD_DEFAULT = "/bin/bash"  # fallback only if $SHELL is not set


def configure_argparser(subparser):
    subparser.add_argument('course_url',
                           help="where to find course description")
    subparser.add_argument('repo_url',
                           help="where to find student input")
    subparser.add_argument('--get', action='store_true',
                           help="pull or clone student repo")
    subparser.add_argument('--put', action='store_true',
                           help="commit pull or clone student repo")


def execute(pargs: argparse.Namespace):
    if os.environ.get(REPOS_HOME_VAR) is None:
        b.critical(f"Environment variable {REPOS_HOME_VAR} must be set (student workdirs directory)")
    home = os.environ.get(REPOS_HOME_VAR)
    checkout_student_repo(pargs.repo_url, home)
    metadatafile = f"{pargs.course_url}/{sdrl.course.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False)
    r.compute_student_work_so_far(course)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    rewrite_submission_file(course, r.SUBMISSION_FILE)
    call_instructor_cmd(course, instructor_cmd())
    validate_submission_file(course, r.SUBMISSION_FILE)
    commit_and_push(course, r.SUBMISSION_FILE)


def checkout_student_repo(repo_url, home):
    """Pulls or clones student repo and changes into its directory."""
    username = git.username_from_repo_url(repo_url)
    os.chdir(home)
    if os.path.exists(username):
        os.chdir(username)
        b.info(f"**** pulled repo in existing directory '{os.getcwd()}'")
        git.pull()
    else:
        git.clone(repo_url, username)
        os.chdir(username)
        b.info(f"**** cloned repo into new directory '{os.getcwd()}'")


def rewrite_submission_file(course: sdrl.course.Course, filename: str):
    """Checks status of entries and inserts different marks where needed."""
    with open(filename, 'rt', encoding='utf8') as f:
        entries = yaml.safe_load(f)
    rewrite_submission_entries(course, entries)
    with open(filename, 'wt', encoding='utf8') as f:
        yaml.safe_dump(entries, f)


def rewrite_submission_entries(course: sdrl.course.Course, entries: tg.Mapping[str, str]):
    """Checks status of entries and inserts different marks where needed."""
    for taskname, mark in entries.items():
        task = course.task(taskname)
        if task is None:
            entries[taskname] = r.NONTASK_MARK
        elif task.accepted:
            entries[taskname] = r.ACCEPT_MARK
        elif task.rejections > 0:
            entries[taskname] += f" (previously rejected {task.rejections}x)"


def instructor_cmd() -> str:
    return os.environ.get(USER_CMD_VAR) or os.environ.get('SHELL', USER_CMD_DEFAULT)


def call_instructor_cmd(course: sdrl.course.Course, cmd: str):
    """Calls user-set command as indicated by environment variables"""
    b.info(f"Will now call the command indicated by the {USER_CMD_VAR} environment variable or else")
    b.info(f"the command indicated by the SHELL environment variable or else {USER_CMD_DEFAULT}.")
    b.info(f"The resulting command in your case will be:  {cmd}")
    b.info("Exit that command (e.g. the shell) to continue with committing and pushing")
    b.info(f"the modified {r.SUBMISSION_FILE}")
    os.system(cmd)


def validate_submission_file(course: sdrl.course.Course, filename: str):
    pass


def commit_and_push():
    assert False, "not yet implemented"