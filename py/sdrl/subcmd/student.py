import argparse
import os
import typing as tg
import readline  # noqa, is active automatically for input()
import requests

import base as b
import git
import sdrl.course
import sdrl.interactive as i
import sdrl.participant
import sdrl.repo as r

meaning = """Reports on course execution so far or prepares submission to instructor."""

def add_arguments(subparser):
    subparser.add_argument('--init', action='store_true',
                           help="start initialization for student repo directory")
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {r.SUBMISSION_FILE} with possible tasks to be checked by instructor")
    subparser.add_argument('--interactive', default="True", action=argparse.BooleanOptionalAction,
                           help="open interactive terminal interface to select tasks to submit")
    subparser.add_argument('--import-keys', action='store_true',
                           help="(re)import all public gpg keys for the given course")
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
        entries = [entry for entry in entries if course.task(entry[0]).remaining_attempts]  # without final rejections
        prepare_submission_file(course, student.root, entries, pargs.interactive)
    elif pargs.import_keys:
        r.import_gpg_keys(course.instructors)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def init():
    data = {}
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
        b.critical(f"Error fetching URL '{metadatafile}'.")
    init_data = coursedata.get('init_data') or {}
    prompts = sdrl.participant.Student.prompts(init_data.get('studentprompts') or {})
    for value in prompts:
        data[value] = input(prompts[value] + ": ")
    b.spit_yaml(sdrl.participant.PARTICIPANT_FILE, data)
    b.info(f"wrote '{sdrl.participant.PARTICIPANT_FILE}'. Now commit and push it.")
    if not(coursedata.get('instructors')):
        b.warning("No information about instructors present. Skipping key import.")
        return
    gpgimportwarning = init_data.get('gpgimportwarning') or """
        Next step is the import of the public keys from the instructors of the course.
        This is necessary to correctly show your progress.
        Press <Enter> to continue or Q <Enter> to abort:  """
    response = input(gpgimportwarning)
    if response and response in "Qq":
        b.critical("Abort.")
    r.import_gpg_keys(coursedata['instructors'])


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
    b.info(f"1. Commit it with commit message '{r.SUBMISSION_COMMIT_MSG}'. Push it.")
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
            ra_string += f"{i.REJECT_SYMBOL*task.rejections}"
            remaining = task.remaining_attempts
            allowed = task.allowed_attempts
            ra_string += f" ({remaining} of {allowed} remain)" if not task.accepted else ""
            if not remaining:
                ra_string = f"{r.REJECT_MARK} (after {allowed} attempt{b.plural_s(allowed)})"
        table.add_row(taskname, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string)
        if out is not None:
            out.append((taskname, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string))
    # table.add_section()
    table.add_row("[b]=TOTAL[/b]", "[b]%6.2f[/b]" % workhours_total, "[b]%6.2f[/b]" % timevalue_total, "")
    b.info(table)


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
