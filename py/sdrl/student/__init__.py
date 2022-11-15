import argparse
import re
import typing as tg

import sdrl.git
import sdrl.course

help = """Reports on course execution so far, in particular how many hours worth of accepted tasks a student has accumulated. 
"""

def configure_argparser(subparser):
    subparser.add_argument('where',
                           help="where to find course description")


def execute(pargs: argparse.Namespace):
    metadatafile = f"{pargs.where}/{sdrl.course.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False)
    commits = sdrl.git.get_commits()
    workhours = get_workhours(commits)
    for taskname, workhours in sorted(workhours):
        if taskname in course.taskdict:
            task = course.taskdict[taskname]
            task.workhours += workhours
        else:
            pass  # ignore non-existing tasknames quietly
    print("Your work so far:")
    workhours_total = 0.0
    timevalue_total = 0.0
    for taskname in sorted((t.slug for t in course.all_tasks())):
        task = course.taskdict[taskname]
        if task.workhours != 0.0:
            workhours_total += task.workhours
            timevalue_total += task.effort
            print(f"{taskname}\t{task.workhours}  (timevalue: {task.effort})")
    print(f"TOTAL:\t\t{workhours_total}  (timevalue: {timevalue_total})")


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
