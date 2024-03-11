import argparse
import os
import typing as tg
import requests

import base as b
import git
import sdrl.course
import sdrl.interactive as i
import sdrl.participant
import sdrl.repo as r

meaning = """Reports on course execution so far or prepares submission to instructor."""

def add_arguments(subparser):
    subparser.add_argument('--init', action=argparse.BooleanOptionalAction,
                           help="start initialization for student repo directory")
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {r.SUBMISSION_FILE} with possible tasks to be checked by instructor")
    subparser.add_argument('--interactive', default="True", action=argparse.BooleanOptionalAction,
                           help="open interactive terminal interface to select tasks to submit")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    if pargs.init:
        init()
        return
    student = sdrl.participant.Student()
    metadatafile = f"{student.course_url}/{b.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False, include_stage="")
    r.compute_student_work_so_far(course)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    if pargs.submission:
        entries = [entry for entry in entries if not(course.task(entry[0]).open_rejections()[1])] #filter final rejections
        prepare_submission_file(course, student.root, entries, pargs.interactive)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def init():
    data = {}
    while True:
        data['course_url'] = os.path.dirname(input("Course URL: "))
        metadatafile = f"{data['course_url']}/{b.METADATA_FILE}"
        try:
            if metadatafile.startswith("file:///"):
                data['course_url'] = data['course_url'][7:]
                coursedata = b.slurp_json(metadatafile[7:])
            else:
                resp = requests.get(url=metadatafile)
                coursedata = resp.json()
        except:
            accept = input("Error fetching URL. Continue anyways? [yN] ")
            if not(accept.startswith("y") or accept.startswith("Y")):
                continue
        break
    init_data = coursedata.get('init_data') or {}
    prompts = sdrl.participant.Student.prompts(init_data.get('studentprompts') or {})
    for value in prompts:
        data[value] = input(prompts[value] + ": ")
    b.spit_yaml("student.yaml", data)


def prepare_submission_file(course: sdrl.course.Course, root: str, entries: tg.Sequence[r.ReportEntry], interactive: bool = False):
    if interactive:
        entries = i.select_entries(entries)
    if not(entries):
        b.info("No entries to submit.")
        return
    # ----- write file:
    b.spit_yaml(os.path.join(root, r.SUBMISSION_FILE), r.submission_file_entries(course, entries))
    b.info(f"Wrote file '{r.SUBMISSION_FILE}'.")
    # ----- give instructions for next steps:
    b.info(f"1. Commit it with commit message '{r.SUBMISSION_COMMIT_MSG}'.")
    b.info(f"2. Then send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  sedrila instructor {git.origin_remote_of_local_repo()}")
    show_instructors(course)


def report_student_work_so_far(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                               workhours_total: float, timevalue_total: float, out = None):
    b.info("Your work so far:")
    table = b.Table()
    table.add_column("Taskname")
    table.add_column("Workhours", justify="right")
    table.add_column("Timevalue", justify="right")
    table.add_column("reject/accept")
    for taskname, workhours, timevalue, rejections, accepted in entries:
        task = course.taskdict[taskname]
        ra_string = (i.ACCEPT_SYMBOL + " ") if task.accepted else ""
        if task.rejections > 0:
            ra_string += f"{i.REJECT_SYMBOL}*{task.rejections}"
            (open_rejections, blocked) = task.open_rejections()
            ra_string += "" if open_rejections < 0 else f"/{open_rejections+task.rejections}"
            if blocked:
                ra_string = r.REJECT_MARK
        table.add_row(taskname, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string)
        if out is not None:
            out.append((taskname, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string))
    # table.add_section()
    table.add_row("[b]=TOTAL[/b]", "[b]%5.2f[/b]" % workhours_total, "[b]%5.2f[/b]" % timevalue_total, "")
    b.info(table)


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
