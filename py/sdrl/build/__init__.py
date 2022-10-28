import argparse

help = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

def configure_argparser(subparser):
    subparser.add_argument('targetdir',
                           help="Directory to which output will be written")


def execute(pargs: argparse.Namespace):
    print("'build' subcommand is not yet implemented")

