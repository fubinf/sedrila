import argparse
import os

import base as b
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
    validate_submission_file()


def checkout_student_repo(repo_url, home):
    pass


def validate_submission_file():
    pass
