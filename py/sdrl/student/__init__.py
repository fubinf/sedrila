import argparse

help = """Reports on course execution so far, in particular how many hours worth of accepted tasks a student has accumulated. 
"""

def configure_argparser(subparser):
    subparser.add_argument('where',
                           help="where to find input")


def execute(pargs: argparse.Namespace):
    print("'student' subcommand is not yet implemented")

