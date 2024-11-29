import argparse
import os
import typing as tg
import readline  # noqa, is active automatically for input()

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.interactive as i
import sdrl.participant
import sdrl.repo as r


meaning = """Reports on course execution so far or prepares submission to instructor."""


def add_arguments(subparser):
    subparser.add_argument('--init', action='store_true',
                           help="start initialization for student repo directory")
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {c.SUBMISSION_FILE} with possible tasks to be checked by instructor")
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
    course = sdrl.course.CourseSI(configdict=student.metadatadict, context=student.metadata_url)
    commits = git.commits_of_local_repo(reverse=True)
    r.compute_student_work_so_far(course, commits)
    entries, workhours_total, timevalue_total = r.student_work_so_far(course)
    if pargs.submission:
        entries = [entry for entry in entries 
                   if course.task(entry.taskname).remaining_attempts]  # without final rejections
        prepare_submission_file(course, student.root, entries, pargs.interactive)
    elif pargs.import_keys:
        r.import_gpg_keys(course.instructors)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def init():
    course_url = os.path.dirname(input("Course URL: "))
    metadata = sdrl.participant.Student.get_metadata(course_url)
    init_data = metadata.get('init_data') or {}  # noqa
    prompts = sdrl.participant.Student.prompts(init_data.get('studentprompts') or {})
    data = dict(course_url=course_url)
    for value in prompts:
        data[value] = input(prompts[value] + ": ")
    b.spit_yaml(c.PARTICIPANT_FILE, data)
    b.info(f"wrote '{c.PARTICIPANT_FILE}'. Now commit and push it.")
    if not(metadata.get('instructors')):
        b.warning("No information about instructors present. Skipping key import.")
        return
    gpgimportwarning = init_data.get('gpgimportwarning') or """
        Next step is the import of the public keys from the instructors of the course.
        This is necessary to correctly show your progress.
        Press <Enter> to continue or Q <Enter> to abort:  """
    response = input(gpgimportwarning)
    if response and response in "Qq":
        b.critical("Abort.")
    r.import_gpg_keys(metadata['instructors'])


def prepare_submission_file(course: sdrl.course.Course, root: str, 
                            entries: tg.Sequence[r.ReportEntry], interactive: bool = False):
    if interactive:
        entries = sorted(entries, key=lambda e: e.taskpath)  # sort by chapter+taskgroup
        entries = i.select_entries(entries)
    if not entries:
        b.info("No entries to submit.")
        return
    # ----- write file:
    b.spit_yaml(os.path.join(root, c.SUBMISSION_FILE), r.submission_file_entries(entries))
    b.info(f"Wrote file '{c.SUBMISSION_FILE}'.")
    # ----- give instructions for next steps:
    b.info(f"1. Commit it with commit message '{c.SUBMISSION_COMMIT_MSG}'. Push it.")
    b.info(f"2. Then send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  sedrila instructor {git.origin_remote_of_local_repo()}")
    show_instructors(course)


def report_student_work_so_far(course: sdrl.course.Course, entries: tg.Sequence[r.ReportEntry],
                               workhours_total: float, timevalue_total: float, out=None):
    b.info("Your work so far:")
    table = b.Table()
    table.add_column("Taskname")
    table.add_column("Workhours", justify="right")
    table.add_column("Timevalue", justify="right")
    table.add_column("reject/accept")
    entries = sorted(entries, key=lambda e: e.taskpath)  # sort by chapter+taskgroup
    for taskname, taskpath, workhours, timevalue, rejections, accepted in entries:
        task = course.taskdict[taskname]
        ra_string = (c.INTERACT_ACCEPT_SYMBOL + " ") if task.is_accepted else ""
        if task.rejections > 0:
            ra_string += f"{c.INTERACT_REJECT_SYMBOL * task.rejections}"
            remaining = task.remaining_attempts
            allowed = task.allowed_attempts
            ra_string += f" ({remaining} of {allowed} remain)" if not task.is_accepted else ""
            if not remaining:
                ra_string = f"{c.SUBMISSION_REJECT_MARK} (after {allowed} attempt{b.plural_s(allowed)})"
        table.add_row(taskpath, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string)
        if out is not None:
            out.append((taskname, "%4.2f" % workhours, "%4.2f" % timevalue, ra_string))
    # table.add_section()
    table.add_row("[b]=TOTAL[/b]", "[b]%6.2f[/b]" % workhours_total, "[b]%6.2f[/b]" % timevalue_total, "")
    b.rich_print(table)


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
