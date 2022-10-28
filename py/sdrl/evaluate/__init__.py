import argparse

help = """Helps teaching assistants evaluate a student's submission of several finished tasks.
"""

def configure_argparser(subparser):
    subparser.add_argument('where',
                           help="where to find student input")


def execute(pargs: argparse.Namespace):
    print("'evaluate' subcommand is not yet implemented")

