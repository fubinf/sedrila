

import argparse
import click

from .student import student_command
import base as b

# for command to show up in old system
meaning = """Temporary subcommand for the new CLI"""
def add_arguments(_): pass
def execute(_: argparse.Namespace): assert False, "this is only intended as a dummy"
# ---------------------------

@click.group()
@click.version_option()
@click.option(
    "--log", default="INFO",
    help="Log level for logging to stdout",
    type=click.Choice([*b.loglevels.keys()])
)
def ui2(log):
    b.set_loglevel(log)
    print("hi from ui2")

ui2.add_command(student_command)


