import argparse
import contextlib
import os
import readline  # noqa, is active automatically for input()

import blessed

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.participant
import sdrl.repo as r
import sdrl.webapp


meaning = """Reports on course execution so far or prepares submission to instructor."""


def add_arguments(subparser):
    subparser.add_argument('workdir', nargs='*',
                           help="where to find student input")
    subparser.add_argument('--init', action='store_true',
                           help="start initialization for student repo directory")
    subparser.add_argument('--op', default="", choices=OP_CMDS.keys(),
                           help="Perform one operation non-interactively")
    subparser.add_argument('--port', '-p', type=int, default=sdrl.webapp.DEFAULT_PORT,
                           help=f"webapp will listen on this port (default: {sdrl.webapp.DEFAULT_PORT})")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    if not pargs.workdir:
        pargs.workdir = ['.']
    pargs.workdir = [wd.rstrip("/") for wd in pargs.workdir]  # make names canonical
    # ----- --init:
    if pargs.init:
        init(pargs.workdir)
        return
    # ----- prepare:
    try:
        for workdir in pargs.workdir:
            if not os.path.isdir(workdir):
                b.critical(f"directory '{workdir}' does not exist.")
        context = sdrl.participant.make_context(pargs, pargs.workdir, is_instructor=False, show_size=True)
    except KeyboardInterrupt:
        print("  Bye.")
        return  # quit
    # ----- execute:
    if pargs.op:
        OP_CMDS[pargs.op](context)  # execute one command via lookup table, with duck-typed arg
    else:
        run_command_loop(context)


def init(workdirs: list[str]):
    if workdirs:
        b.critical("--init can only be called without an explicit argument from within a working directory")
    sdrl.participant.Student.build_participant_file()
    student = sdrl.participant.Student('.', is_instructor=False)
    if not(student.course_metadata.get('instructors')):
        b.warning("No information about instructors present in course. Skipping key import.")
        return
    gpgimportwarning = """
        Next step is the import of the public keys of the course instructors.
        This is necessary to correctly show your progress.
        Press <Enter> to continue or Q <Enter> to abort:  """
    response = input(gpgimportwarning)
    if response and response in "Qq":
        b.critical("Abort.")
    r.import_gpg_keys(student.course_metadata['instructors'])


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


def cmd_prepare(ctx: sdrl.participant.Context):
    for student in ctx.studentlist:
        b.info(f"----- Collect tasks for '{student.submissionfile_path}'")
        # ----- keep only valid CHECK entries in submission:
        for taskname in list(student.submission.keys()):  # work on a copy
            task = student.course.task(taskname)
            if not task:
                b.warning(f"'{taskname}' is not a valid task name. Ignored.")
            eligible = (task.remaining_attempts > 0 and not task.is_accepted)
            is_a_check_entry = (student.submission[taskname] == c.SUBMISSION_CHECK_MARK)
            if not task or not eligible or not is_a_check_entry:
                del student.submission[taskname]
        # ----- add all eligible NONCHECK entries:
        for taskname, task in student.course.taskdict.items():
            eligible = (task.workhours > 0 and task.remaining_attempts > 0 and not task.is_accepted)
            if eligible and taskname not in student.submission:
                student.submission[taskname] = c.SUBMISSION_NONCHECK_MARK
        student.save_submission()


def cmd_webapp(ctx: sdrl.participant.Context):
    b.info("----- Start webapp to accept/reject submissions")
    sdrl.webapp.run(ctx)


def cmd_edit(ctx: sdrl.participant.Context):
    editorcmd = ''
    b.info(f"----- Edit '{c.SUBMISSION_FILE}'")
    for workdir in ctx.students:
        if b.yesses("Edit '%s'?", [workdir], yes_if_1=(len(ctx.students) == 1)):
            editorcmd = os.environ.get('EDITOR', editorcmd)
            if not editorcmd:
                b.info(f"Environment variable EDITOR not set, using '{c.EDITOR_CMD_DEFAULT}'")
                editorcmd = c.EDITOR_CMD_DEFAULT
            os.system(f"{editorcmd} {workdir}/{c.SUBMISSION_FILE}")


def cmd_commit(ctx: sdrl.participant.Context):
    b.info(f"----- Commit '{c.SUBMISSION_FILE}'")
    yesses = b.yesses("Commit '%s'?", ctx.students, yes_if_1=True)
    for yes, workdir in zip(yesses, ctx.students):
        if yes:
            b.info(f"Committing '{workdir}/{c.SUBMISSION_FILE}'")
            with contextlib.chdir(workdir):
                git.commit(*[c.SUBMISSION_FILE], msg=c.SUBMISSION_COMMIT_MSG, signed=True)
        else:
            b.info(f"Not committing '{workdir}/{c.SUBMISSION_FILE}'.")


def cmd_push(ctx: sdrl.participant.Context):
    b.info("----- Push recent commits")
    yesses = b.yesses("Push '%s'?", ctx.students)
    for yes, workdir in zip(yesses, ctx.students):
        if yes:
            b.info(f"Pushing '{workdir}/{c.SUBMISSION_FILE}' etc.")
            with contextlib.chdir(workdir):
                git.push()
        else:
            b.info(f"Not pushing '{workdir}/{c.SUBMISSION_FILE}'.")
    b.info(f"Now send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  #  {ctx.course_url}")
    b.info(f"  sedrila instructor {' '.join([s.student_gituser for s in ctx.studentlist])}")
    _show_instructors(ctx.course)


MENU = "\n>>> p:prepare  w:webapp  e:edit  c:commit  u:push  q:quit  h:help  "
MENU_HELP = f"""
  prepare: create or update {c.SUBMISSION_FILE} for selecting/unselecting tasks via the webapp
  webapp:  view file tree(s) and course progress in browser, select tasks to be submitted
  edit:    manually edit  {c.SUBMISSION_FILE} to include tasks sedrila cannot recognize
  commit:  commit {c.SUBMISSION_FILE} with proper commit message for submission
  push:    push commits and show instructions for announcing your submission
  Can work on your work directory or on yours and your partner's if you put them side-by-side
  below the same parent directory.
"""
MENU_CMDS = dict(p=cmd_prepare, w=cmd_webapp, e=cmd_edit, c=cmd_commit, u=cmd_push)
OP_CMDS = dict(prepare=cmd_prepare, webapp=cmd_webapp, edit=cmd_edit)


def _show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")
