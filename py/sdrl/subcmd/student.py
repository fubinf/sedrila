import argparse
import re
import typing as tg

import yaml

import base as b
import git
import sdrl.course
import sdrl.repo as r

help = """Reports on course execution so far or prepares submission to instructor."""

def configure_argparser(subparser):
    subparser.add_argument('course_url',
                           help="where to find course description")
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {r.SUBMISSION_FILE} with possible tasks to be checked by instructor")


def execute(pargs: argparse.Namespace):
    metadatafile = f"{pargs.course_url}/{sdrl.course.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False)
    commits = git.get_commits()
    workhours = r.get_workhours(commits)
    r.accumulate_workhours_per_task(workhours, course)
    hashes = r.get_submission_checked_commits(course, commits)
    checked_tuples = r.get_all_checked_tuples(hashes)
    r.accumulate_timevalues_and_attempts(checked_tuples, course)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    if pargs.submission:
        prepare_submission_file(course, entries, pargs.course_url)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def prepare_submission_file(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                            course_url: str):
    # ----- write file:
    with open(r.SUBMISSION_FILE, 'wt', encoding='utf8') as f:
        yaml.safe_dump(r.submission_file_entries(course, entries), f)
    b.info(f"Wrote file '{r.SUBMISSION_FILE}'.")
    # ----- give instructions for next steps:
    b.info(f"1. Remove all entries from it that you do not want to submit yet.")
    b.info(f"2. Commit it with commit message '{r.SUBMISSION_COMMIT_MSG}'.")
    b.info(f"3. Then send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  sedrila instructor --submission {course_url} {git.get_remote_origin()}")
    show_instructors(course)


def report_student_work_so_far(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                               workhours_total: float, timevalue_total: float):
    print("Your work so far:")
    print("taskname\t\tworkhours\ttimevalue\treject/accept")
    for taskname, workhours, timevalue, rejections, accepted in entries:
        task = course.taskdict[taskname]
        ra_list = task.rejections * [r.REJECT_MARK] + ([r.ACCEPT_MARK] if task.accepted else [])
        ra_string = ", ".join(ra_list)
        print(f"{taskname}\t{workhours}\t{timevalue}\t{ra_string}")
    print(f"TOTAL:\t\t{workhours_total}\t{timevalue_total}")


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
