import argparse
import os
import tempfile

import base as b
import git
import sdrl.course
import sdrl.repo as r

help = """Help instructors evaluate a student's submission of several finished tasks.
"""

REPOS_HOME_VAR = "STUDENT_REPOS_HOME"


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
    validate_submission_file()


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


def validate_submission_file():
    assert False, "not yet implemented"
