"""Top-level definition of command-line interface."""
import argparse
import click

from .student import student_command
from .instructor import instructor_command
from .author import author_command
from .maintainer import maintainer_command
from .evaluator import evaluator_command
from .server import server_command
import base as b


@click.group()
@click.version_option()
@click.option(
    "--log", default="INFO",
    help="Log level for logging to stdout",
    type=click.Choice([*b.loglevels.keys()])
)
def cli(log):
    b.set_loglevel(log)


cli.add_command(student_command)
cli.add_command(instructor_command)
cli.add_command(author_command)
cli.add_command(maintainer_command)
cli.add_command(evaluator_command)
cli.add_command(server_command)
