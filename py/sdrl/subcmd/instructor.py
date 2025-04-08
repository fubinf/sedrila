import argparse
import contextlib
import os
import typing as tg

import base as b
import sgit
import sdrl.constants as c
import sdrl.course
import sdrl.participant
import sdrl.repo as r
import sdrl.webapp

meaning = """Help instructors evaluate students' submissions of several finished tasks.
"""


def add_arguments(subparser):
    subparser.add_argument('workdir', nargs='+',
                           help="where to find student input")
    subparser.add_argument('--op', default="", choices=OP_CMDS.keys(),
                           help="Perform one operation non-interactively")
    subparser.add_argument('--port', '-p', type=int, default=sdrl.webapp.DEFAULT_PORT,
                           help=f"webapp will listen on this port (default: {sdrl.webapp.DEFAULT_PORT})")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    pargs.workdir = [wd.rstrip("/") for wd in pargs.workdir]  # make names canonical
    # ----- prepare:
    try:
        for workdir in pargs.workdir:
            if not os.path.isdir(workdir):
                b.critical(f"directory '{workdir}' does not exist.")
            prepare_workdir(workdir)
        context = sdrl.participant.make_context(pargs, pargs.workdir, is_instructor=True, show_size=True)
    except KeyboardInterrupt:
        print("  Bye.")
        return  # quit
    # ----- execute:
    if pargs.op:
        OP_CMDS[pargs.op](context)  # execute one command via lookup table, with duck-typed arg
    else:
        run_command_loop(context, MENU, MENU_HELP, MENU_CMDS)


def run_command_loop(context, menu: str, helptext: str, cmds: dict[str, tg.Callable]):
    import sdrl.subcmd.student
    sdrl.subcmd.student.run_command_loop(context, menu, helptext, cmds)


def cmd_webapp(ctx: sdrl.participant.Context):
    b.info("----- Start webapp to accept/reject submissions")
    sdrl.webapp.run(ctx)


def cmd_edit(ctx: sdrl.participant.Context):
    import sdrl.subcmd.student
    sdrl.subcmd.student.cmd_edit(ctx)


def cmd_commit_and_push(ctx: sdrl.participant.Context):
    b.info("----- Commit and push student repos")
    yesses = b.yesses("Commit & Push '%s'?", ctx.students)
    for yes, workdir in zip(yesses, ctx.students):
        if yes:
            b.info(f"Committing and pushing '{workdir}/{c.SUBMISSION_FILE}'")
            with contextlib.chdir(workdir):
                sgit.make_commit(*[c.SUBMISSION_FILE], msg=c.SUBMISSION_CHECKED_COMMIT_MSG, signed=True)
                sgit.push()
        else:
            b.info(f"Not committing '{workdir}/{c.SUBMISSION_FILE}'.")


def prepare_workdir(workdir: str):
    b.info(f"----- Prepare '{workdir}'")
    with contextlib.chdir(workdir):
        # ----- obtain instructor key fingerprints:
        if not os.path.isfile(c.PARTICIPANT_FILE):
            b.critical(f"'{workdir}': '{c.PARTICIPANT_FILE}' is missing.")
        S = sdrl.participant.Student  # abbrev
        course = S.get_course_metadata(S.get_course_url(c.PARTICIPANT_FILE))
        key_fingerprints = { i.get('keyfingerprint', '') for i in course.get('instructors', [])}
        key_fingerprints.discard('')  # empty entry would mean unsigned commits are considered instructor-signed
        # ----- consider pulling:
        state = r.submission_state('.', key_fingerprints)
        if state == c.SUBMISSION_STATE_CHECKED:
            b.info(f"--- Pulling repo")
            sgit.pull()
        # ----- consider filtering:
        state = r.submission_state('.', key_fingerprints)
        if state == c.SUBMISSION_STATE_FRESH:
            b.info(f"--- Filtering '{c.SUBMISSION_FILE}'")
            submission = {k:v for k, v in b.slurp_yaml(c.SUBMISSION_FILE).items()
                          if v == c.SUBMISSION_CHECK_MARK}
            b.spit_yaml(c.SUBMISSION_FILE, submission)


MENU = "\n>>> w:webapp e:edit c:commit+push q:quit   "
MENU_CMDS = dict(w=cmd_webapp, e=cmd_edit, c=cmd_commit_and_push)
MENU_HELP = ""
OP_CMDS = dict(webapp=cmd_webapp, edit=cmd_edit, commit_and_push=cmd_commit_and_push)
