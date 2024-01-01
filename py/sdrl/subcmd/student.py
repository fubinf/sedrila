import argparse
import typing as tg

import base as b
import git
import sdrl.course
import sdrl.participant
import sdrl.repo as r

help = """Reports on course execution so far or prepares submission to instructor."""

def configure_argparser(subparser):
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {r.SUBMISSION_FILE} with possible tasks to be checked by instructor")


def execute(pargs: argparse.Namespace):
    student = sdrl.participant.Student()
    metadatafile = f"{student.course_url}/{b.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False, include_stage="")
    r.compute_student_work_so_far(course)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    if pargs.submission:
        prepare_submission_file(course, entries, pargs.course_url)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def prepare_submission_file(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                            course_url: str):
    # ----- write file:
    b.spit_yaml(r.SUBMISSION_FILE, r.submission_file_entries(course, entries))
    b.info(f"Wrote file '{r.SUBMISSION_FILE}'.")
    # ----- give instructions for next steps:
    b.info(f"1. Remove all entries from it that you do not want to submit yet.")
    b.info(f"2. Commit it with commit message '{r.SUBMISSION_COMMIT_MSG}'.")
    b.info(f"3. Then send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  sedrila instructor --submission {course_url} {git.origin_remote_of_local_repo()}")
    show_instructors(course)


def report_student_work_so_far(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                               workhours_total: float, timevalue_total: float):
    b.info("Your work so far:")
    table = b.Table()
    table.add_column("Taskname")
    table.add_column("Workhours", justify="right")
    table.add_column("Timevalue", justify="right")
    table.add_column("reject/accept")
    for taskname, workhours, timevalue, rejections, accepted in entries:
        task = course.taskdict[taskname]
        ra_list = task.rejections * [r.REJECT_MARK] + ([r.ACCEPT_MARK] if task.accepted else [])
        ra_string = ", ".join(ra_list)
        table.add_row(taskname, "%4.1f" % workhours, "%4.1f" % timevalue, ra_string)
    # table.add_section()
    table.add_row("[b]=TOTAL[/b]", "[b]%5.1f[/b]" % workhours_total, "[b]%5.1f[/b]" % timevalue_total, "")
    b.info(table)


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
