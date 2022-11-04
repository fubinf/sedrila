import argparse

help = """How far am I? Determines how many hours worth of accepted tasks a student has accumulated so far. 
"""

def configure_argparser(subparser):
    subparser.add_argument('where',
                           help="where to find input")


def execute(pargs: argparse.Namespace):
    print("'howfarami' subcommand is not yet implemented")

