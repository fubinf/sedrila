"""
Logic for handling information coming from git repos: 
effort commits, submissions, submission checks.
"""
import re
import subprocess as sp
import typing as tg

import yaml

import base as b
import git
import sdrl.course

SUBMISSION_FILE = "submission.yaml"
SUBMISSION_COMMIT_MSG = "submission.yaml"
SUBMISSION_CHECKED_COMMIT_MSG = "submission.yaml checked"
CHECK_MARK = "CHECK"
ACCEPT_MARK = "ACCEPT"
REJECT_MARK = "REJECT"
NONTASK_MARK = "NO_SUCH_TASKNAME"

CheckedTuple = tg.Tuple[str, str, str]  # hash, taskname, tasknote
WorkEntry = tg.Tuple[str, float]  # taskname, workhours
ReportEntry = tg.Tuple[str, float, float, int, bool]  # taskname, workhoursum, timevalue, rejections, accepted


def accumulate_timevalues_and_attempts(checked_tuples: tg.Sequence[CheckedTuple], course: sdrl.course.Course):
    """Reflect the check_tuples data in the course data structure."""
    for refid, taskname, tasknote in checked_tuples:
        b.debug(f"tuple: {refid}, {taskname}, {tasknote}")
        task = course.task(taskname)
        if tasknote.startswith(ACCEPT_MARK):
            if not task.remaining_attempts:
                b.warning(f"Cannot accept task that has consumed its allowed attempts: {taskname}")
            else:
                task.accepted = True
                b.debug(f"{taskname} accepted")
        elif tasknote.startswith(REJECT_MARK):
            task.rejections += 1
            b.debug(f"{taskname} rejected")
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


def checked_tuples_from_commits(hasheslist: list[list[str]]) -> tg.Sequence[CheckedTuple]:
    """Collect the individual checks across all 'submission.yaml checked' commits.
    This will only allow grades for tasks that were actually requested to grade.
    The state of a task should always be the last one in a given group."""
    result = []
    for hashes in hasheslist:
        if not hashes:
            continue
        try:
            gitfile = git.contents_of_file_version(hashes.pop(0), SUBMISSION_FILE, encoding='utf8')
            requested = list(yaml.safe_load(gitfile).keys())
        except Exception:  # noqa
            continue  # no submission file yet, grading isn't possible
        groupdict: dict[str, CheckedTuple] = {}
        for refid in hashes:
            submission = yaml.safe_load(git.contents_of_file_version(refid, SUBMISSION_FILE, encoding='utf8'))
            for taskname, tasknote in submission.items():
                if not(taskname in requested):
                    b.warning(f"Attempted to grade task that wasn't requested: {taskname}")
                    continue
                groupdict[taskname] = (refid, taskname, tasknote)
        result.extend(groupdict.values())
    return result


def import_gpg_keys(instructors: tg.Sequence[b.StrAnyDict]):
    for instructor in instructors:
        if not(instructor.get('pubkey')):
            b.warning("No key present for " + instructor.get('nameish') + ", skipping")
            continue
        b.info("Importing key for " + instructor.get('nameish'))
        if type(instructor['pubkey']) is list:
            instructor['pubkey'] = "\n".join(instructor['pubkey'])
        if not instructor['pubkey'].startswith("-----"):
            instructor['pubkey'] = ("-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
                                    f"\n{instructor['pubkey']}\n"
                                    "-----END PGP PUBLIC KEY BLOCK-----")
        sp.run(["gpg", "--import"], input=instructor['pubkey'], encoding='ascii')


def compute_student_work_so_far(course: sdrl.course.Course):
    """
    Obtain per-task worktimes from student commits and 
    per-task timevalues from submission checked commits.
    Store them in course.
    """
    commits = git.commits_of_local_repo(reverse=True)
    workhours = workhours_of_commits(commits)
    accumulate_workhours_per_task(workhours, course)
    hasheslist = submission_checked_commit_hashes(course, commits)
    checked_tuples = checked_tuples_from_commits(hasheslist)
    accumulate_timevalues_and_attempts(checked_tuples, course)


def submission_checked_commit_hashes(course: sdrl.course.Course,
                                     commits: tg.Sequence[git.Commit]) -> list[list[str]]:
    """List of hashes of properly instructor-signed commits of finished submission checks.
    This will be grouped by consecutively done commits of instructors and student, starting with the grading request."""
    try:
        allowed_signers = [b.as_fingerprint(instructor['keyfingerprint'])
                           for instructor in course.instructors]
    except KeyError:
        b.critical("missing 'keyfingerprint' in configuration")
    group = []
    result = [group]
    student_commit = None
    for commit in commits:
        b.debug(f"commit.subject, fpr: {commit.subject}, {commit.key_fingerprint}")
        right_subject = re.match(SUBMISSION_CHECKED_COMMIT_MSG, commit.subject) is not None
        right_signer = commit.key_fingerprint and b.as_fingerprint(commit.key_fingerprint) in allowed_signers  # noqa
        if not right_signer:
            student_commit = commit
            if group:
                group = []
                result.append(group)
        if right_subject and right_signer and student_commit:
            if not group:
                group.append(student_commit.hash)
            group.append(commit.hash)
    return result


def workhours_of_commits(commits: tg.Sequence[git.Commit]) -> list[WorkEntry]:
    """Extract all pairs of (taskname, workhours) from commit list."""
    result = []
    for commit in commits:
        pair = _parse_taskname_workhours(commit.subject)
        if pair:
            result.append(pair)
    return result


def student_work_so_far(course) -> tg.Tuple[list[ReportEntry], float, float]:
    """Data for work report: per-task entries (worktime, attempts) and totals."""
    workhours_total = 0.0
    timevalue_total = 0.0
    result = []
    for taskname in sorted((t.name for t in course.taskdict.values())):
        task = course.taskdict[taskname]
        if task.workhours != 0.0:
            workhours_total += task.workhours
            if task.accepted:
                timevalue_total += task.timevalue
            result.append((taskname, task.workhours, task.timevalue,
                           task.rejections, task.accepted))  # one result tuple
    return result, workhours_total, timevalue_total  # overall result triple


def submission_file_entries(entries: list[ReportEntry], rejected: list[str] = None) -> dict[str, str]:
    """taskname -> CHECK_MARK  for each yet-to-be-accepted task with effort in any commit."""
    candidates = dict()
    for taskname, workhoursum, timevalue, rejections, accepted in entries:
        if rejected is None:
            if not accepted:
                candidates[taskname] = CHECK_MARK
        else:
            if accepted:
                candidates[taskname] = ACCEPT_MARK
            elif taskname in rejected:
                candidates[taskname] = REJECT_MARK
            else:
                candidates[taskname] = CHECK_MARK
    return candidates


def _parse_taskname_workhours(commit_msg: str) -> tg.Optional[WorkEntry]:
    """Return pair of (taskname, workhours) from commit message if present, or None otherwise."""
    worktime_regexp = (r"\s*[#%](?P<name>[\w.-]+?)\s+"
                       r"(?:(?P<dectime>-?\d+(\.\d+)?)|"
                       r"(?P<hh>-?\d+):(?P<mm>\d\d)) ?h\b")  # %MyTask117 3.5h   %Some-Stuff 3:45h
    mm = re.match(worktime_regexp, commit_msg)
    if not mm:
        return None  # not the format we're looking for
    taskname = mm.group('name')
    if mm.group('dectime'):  # decimal time
        workhours = float(mm.group('dectime'))
    else:
        workhours = float(mm.group('hh')) + float(mm.group('mm')) / 60  # hh:mm format
    return taskname, workhours
