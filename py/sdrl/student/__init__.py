import argparse
import re
import typing as tg

import sdrl.git

help = """Reports on course execution so far, in particular how many hours worth of accepted tasks a student has accumulated. 
"""

def configure_argparser(subparser):
    subparser.add_argument('where',
                           help="where to find input")


def execute(pargs: argparse.Namespace):
    commits = sdrl.git.get_commits()
    workhours = get_workhours(commits)
    for taskname, worktime in sorted(workhours):
        print(f"{taskname}\n{workhours}")
    
    
def get_workhours(commits: tg.Sequence[sdrl.git.Commit]) -> tg.Sequence[tg.Tuple[str, float]]:
    """Extract all pairs of (taskname, workhours) from commit list."""
    result = []
    for commit in commits:
        worktime_regexp = r"(\w+)\s+(\d+(?:\.\d+)) ?h\b"  # "MyTask117 3.5h remainder of commit msg"
        mm = re.match(worktime_regexp, commit.subject)
        if not mm:
            continue  # not the format we're looking for
        taskname, worktime = mm.group(1), float(mm.group(2))
        result.append((taskname, worktime))
    return result
