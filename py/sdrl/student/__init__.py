import argparse
import re
import typing as tg

import yaml

import base as b
import git
import sdrl.course

help = """Reports on course execution so far or prepares submission to instructor."""

SUBMISSION_FILE = "submission.yaml"
SUBMISSION_COMMIT_MSG = "submission.yaml"
SUBMISSION_CHECKED_COMMIT_MSG = "submission.yaml checked"
CHECK_MARK = "CHECK"
ACCEPT_MARK = "ACCEPT"
REJECT_MARK = "REJECT"

CheckedTuple = tg.Tuple[str, str, str]  # hash, taskname, tasknote
WorkEntry = tg.Tuple[str, float]  # taskname, workhours
ReportEntry = tg.Tuple[str, float, float, int, bool]  # taskname, workhoursum, timevalue, rejections, accepted

def configure_argparser(subparser):
    subparser.add_argument('course_url',
                           help="where to find course description")
    subparser.add_argument('--submission', action='store_true',
                           help=f"generate {SUBMISSION_FILE} with possible tasks to be checked by instructor")


def execute(pargs: argparse.Namespace):
    metadatafile = f"{pargs.course_url}/{sdrl.course.METADATA_FILE}"
    course = sdrl.course.Course(metadatafile, read_contentfiles=False)
    commits = git.get_commits()
    workhours = get_workhours(commits)
    accumulate_workhours_per_task(workhours, course)
    hashes = get_submission_checked_commits(course, commits)
    checked_tuples = get_all_checked_tuples(hashes)
    accumulate_timevalues_and_attempts(checked_tuples, course)
    entries, workhours_total, timevalue_total = student_work_so_far(course)
    if pargs.submission:
        prepare_submission_file(course, entries, pargs.course_url)
    else:
        report_student_work_so_far(course, entries, workhours_total, timevalue_total)


def accumulate_timevalues_and_attempts(checked_tuples: tg.Sequence[CheckedTuple], course: sdrl.course.Course):
    """Reflect the check_tuples data in the course data structure."""
    for refid, taskname, tasknote in checked_tuples:
        print("tuple:", refid, taskname, tasknote)
        task = course.task(taskname)
        if tasknote.startswith(ACCEPT_MARK):
            task.accepted = True
            print(taskname, "accepted")
        elif tasknote.startswith(REJECT_MARK):
            task.rejections += 1
            print(taskname, "rejected")
        else:
            pass  # unmodified entry: instructor has not checked it
            

def accumulate_workhours_per_task(workentries: tg.Sequence[WorkEntry], course: sdrl.course.Course):
    """Reflect the workentries data in the course data structure."""
    for taskname, workhours in sorted(workentries):
        if taskname in course.taskdict:
            task = course.taskdict[taskname]
            task.workhours += workhours
        else:
            pass  # ignore non-existing tasknames quietly


def get_all_checked_tuples(hashes: tg.Sequence[str]) -> tg.Sequence[CheckedTuple]:
    """Collect the individual checks across all 'submission.yaml checked' commits."""
    result = []
    for refid in hashes:
        submission = yaml.safe_load(git.get_file_version(refid, SUBMISSION_FILE, encoding='utf8'))
        for taskname, tasknote in submission['submission'].items():
            result.append((refid, taskname, tasknote))
    return result


def get_submission_checked_commits(course: sdrl.course.Course,
                                   commits: tg.Sequence[git.Commit]) -> tg.Sequence[str]:
    """List of hashes of properly instructor-signed commits of finished submission checks."""
    allowed_signers = [b.as_fingerprint(instructor['keyfingerprint']) 
                       for instructor in course.instructors]
    result = []
    for commit in commits:
        b.debug(f"commit.subject, fpr: {commit.subject}, {commit.key_fingerprint}")
        right_subject = re.match(SUBMISSION_CHECKED_COMMIT_MSG, commit.subject) is not None
        right_signer = commit.key_fingerprint and b.as_fingerprint(commit.key_fingerprint) in allowed_signers
        if right_subject and right_signer:
            result.append(commit.hash)
    return result


def get_workhours(commits: tg.Sequence[git.Commit]) -> tg.Sequence[WorkEntry]:
    """Extract all pairs of (taskname, workhours) from commit list."""
    result = []
    for commit in commits:
        pair = parse_taskname_workhours(commit.subject)
        if pair:
            result.append(pair)
    return result


def parse_taskname_workhours(commit_msg: str) -> tg.Optional[WorkEntry]:
    """Return pair of (taskname, workhours) from commit message if present, or None otherwise."""
    worktime_regexp = r"(\w+)\s+(?:(\d+(?:\.\d+)?)|(\d+):(\d\d)) ?h\b"  # "MyTask117 3.5h" or "SomeStuff 3:45h"
    mm = re.match(worktime_regexp, commit_msg)
    if not mm:
        return None  # not the format we're looking for
    taskname = mm.group(1)
    if mm.group(2):  # decimal time
        workhours = float(mm.group(2))
    else:
        workhours = float(mm.group(3)) + float(mm.group(4)) / 60  # hh:mm format
    return (taskname, workhours)


def prepare_submission_file(course: sdrl.course.Course, entries: tg.Sequence[ReportEntry],
                            course_url: str):
    #----- write file:
    with open(SUBMISSION_FILE, 'wt', encoding='utf8') as f:
        yaml.safe_dump(submission_file_entries(course, entries), f)
    b.info(f"Wrote file '{SUBMISSION_FILE}'.")
    #----- give instructions for next steps:
    b.info(f"1. Remove all entries from it that you do not want to submit yet.")
    b.info(f"2. Commit it with commit message '{SUBMISSION_COMMIT_MSG}'.")
    b.info(f"3. Then send the following to your instructor by email:")
    b.info(f"  Subject: Please check submission")
    b.info(f"  sedrila instructor --submission {course_url} {git.get_remote_origin()}")
    show_instructors(course)


def report_student_work_so_far(course: sdrl.course.Course, entries: tg.Sequence[ReportEntry], 
                               workhours_total: float, timevalue_total: float):
    print("Your work so far:")
    print("taskname\t\tworkhours\ttimevalue\treject/accept")
    for taskname, workhours, timevalue, rejections, accepted in entries:
        task = course.taskdict[taskname]
        ra_list = task.rejections * [REJECT_MARK] + ([ACCEPT_MARK] if task.accepted else [])
        ra_string = ", ".join(ra_list)
        print(f"{taskname}\t{workhours}\t{timevalue}\t{ra_string}")
    print(f"TOTAL:\t\t{workhours_total}\t{timevalue_total}")


def show_instructors(course, with_gitaccount=False):
    b.info("The instructors for this course are:")
    for instructor in course.instructors:
        b.info(f"  {instructor['nameish']} <{instructor['email']}>")
        if with_gitaccount:
            b.info(f"     git account: {instructor['gitaccount']}")


def student_work_so_far(course) -> tg.Tuple[tg.Sequence[ReportEntry], float, float]:
    workhours_total = 0.0
    timevalue_total = 0.0
    result = []
    for taskname in sorted((t.slug for t in course.all_tasks())):
        task = course.taskdict[taskname]
        if task.workhours != 0.0:
            workhours_total += task.workhours
            if task.accepted:
                timevalue_total += task.timevalue
            result.append((taskname, task.workhours, task.timevalue,
                           task.rejections, task.accepted))  # one result tuple
    return (result, workhours_total, timevalue_total)  # overall result triple


def submission_file_entries(course: sdrl.course.Course, entries: tg.Sequence[ReportEntry]
                            ) -> tg.Mapping[str, str]:
    """taskname -> CHECK_MARK  for each yet-to-be-accepted task with effort in any commit."""
    candidates = dict()
    for taskname, workhoursum, timevalue, rejections, accepted in entries:
        if not accepted:
            candidates[taskname] = CHECK_MARK
    return candidates
    
