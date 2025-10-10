"""
Logic for handling information coming from git repos: 
effort commits, submissions, submission checks.
Knows about the respective format conventions.
"""
import contextlib
import datetime as dt
import enum
import os.path
import re
import subprocess as sp
import typing as tg

import yaml

import base as b
import sgit
import sdrl.constants as c
import sdrl.course


class ET(enum.StrEnum):  # EventType
    work = 'work'
    accept = 'accept'
    reject = 'reject'


class Event(tg.NamedTuple):
    evtype: ET
    student: str  # username
    committer: str  # email
    when: dt.datetime
    taskname: str
    timevalue: float


class TaskCheckEntry(tg.NamedTuple):
    commit: sgit.Commit
    taskname: str
    tasknote: str


class WorkEntry(tg.NamedTuple):
    commit: sgit.Commit
    taskname: str
    timevalue: float


class ReportEntry(tg.NamedTuple):
    taskname: str
    taskpath: str
    workhoursum: float
    timevalue: float
    rejections: int
    accepted: bool


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


def event_list(course: sdrl.course.Course, student_username: str, commits: tg.Sequence[sgit.Commit]) -> list[Event]:
    result = []
    instructor_commits = submission_checked_commits(course.instructors, commits)
    for tc_entry in taskcheck_entries_from_commits(instructor_commits):
        commit = tc_entry.commit
        taskname = tc_entry.taskname
        event = Event(ET.accept if is_accepted(tc_entry.tasknote) else ET.reject, 
                      student_username, commit.author_email, commit.author_date, 
                      taskname, course.task(taskname).timevalue)
        result.append(event)
    for work_entry in work_entries_from_commits(commits):
        commit = work_entry.commit
        event = Event(ET.work, 
                      student_username, commit.author_email, commit.author_date, 
                      work_entry.taskname, work_entry.timevalue)
        result.append(event)
    return result


def compute_student_work_so_far(course: sdrl.course.Course, commits: tg.Sequence[sgit.Commit]):
    """
    Obtain per-task worktimes from student commits and 
    per-task timevalues from submission checked commits.
    Store them in course.
    """
    _accumulate_student_workhours_per_task(commits, course)
    all_instructors = course.instructors + course.former_instructors  # treated equally for now
    instructor_commits = submission_checked_commits(all_instructors, commits)
    taskcheck_entries = taskcheck_entries_from_commits(instructor_commits)
    _accumulate_timevalues_and_attempts(taskcheck_entries, course)


def submission_checked_commits(instructors: tg.Sequence[tg.Mapping[str, str]],
                               commits: tg.Sequence[sgit.Commit]) -> list[sgit.Commit]:
    """The properly instructor-signed Commits of finished submission checks."""
    try:
        allowed_signers = {b.as_fingerprint(instructor['keyfingerprint'])
                           for instructor in instructors if 'keyfingerprint' in instructor}
    except KeyError:
        allowed_signers = set()  # silence linter warning
        b.critical("missing 'keyfingerprint' in configuration")
    result = []
    for commit in commits:
        b.debug(f"commit.subject, fpr: {commit.subject}, {commit.key_fingerprint}")
        right_subject = re.match(c.SUBMISSION_CHECKED_COMMIT_MSG, commit.subject) is not None
        if right_subject and is_allowed_signer(commit, allowed_signers):
            result.append(commit)
    return result


def submission_state(workdir: str, instructor_fingerprints: set[str]) -> str:
    """Determines which of SUBMISSION_STATE_FRESH/CHECKING/CHECKED/OTHER applies to the repo in workdir."""
    with contextlib.chdir(workdir):
        # ----- make sure c.SUBMISSION_FILE exists:
        if not os.path.exists(c.SUBMISSION_FILE):
            b.warning(f"'{workdir}': file '{c.SUBMISSION_FILE}' does not exist.")
            return c.SUBMISSION_STATE_OTHER
        # ----- check for case CHECKING:
        if sgit.is_modified(c.SUBMISSION_FILE):
            return c.SUBMISSION_STATE_CHECKING
        # ----- check for case FRESH:
        regexp = '|'.join((re.escape(c.SUBMISSION_COMMIT_MSG), re.escape(c.SUBMISSION_CHECKED_COMMIT_MSG)))
        commit = sgit.find_most_recent_commit(regexp)
        if not commit:  # c.SUBMISSION_FILE was never checked in correctly
            b.warning(f"'{workdir}': No commit found with message  '{c.SUBMISSION_COMMIT_MSG}'.")
            return c.SUBMISSION_STATE_OTHER
        if commit.subject == c.SUBMISSION_COMMIT_MSG:
            return c.SUBMISSION_STATE_FRESH
        # ----- check for case CHECKED:
        assert commit.subject == c.SUBMISSION_CHECKED_COMMIT_MSG
        if commit.key_fingerprint in instructor_fingerprints:
            return c.SUBMISSION_STATE_CHECKED
        # ----- the final remaining case of OTHER:
        b.warning(f"'{workdir}': Commit with message  '{c.SUBMISSION_CHECKED_COMMIT_MSG}' is not signed by instructor.")
        return c.SUBMISSION_STATE_OTHER


def is_allowed_signer(commit: sgit.Commit, allowed_signers: set[str]) -> bool:
    return commit.key_fingerprint and b.as_fingerprint(commit.key_fingerprint) in allowed_signers  


def taskcheck_entries_from_commits(instructor_commits: list[sgit.Commit]) -> tg.Sequence[TaskCheckEntry]:
    """
    Collect the individual entries for all 'submission.yaml checked' commits.
    """
    result = []
    for commit in instructor_commits:
        checks = yaml.safe_load(sgit.contents_of_file_version(commit.hash, c.SUBMISSION_FILE, encoding='utf8'))
        for taskname, tasknote in checks.items():
            result.append(TaskCheckEntry(commit, taskname, tasknote))
    return result


def work_entries_from_commits(commits: tg.Iterable[sgit.Commit]) -> tg.Sequence[WorkEntry]:
    """
    Collect the individual entries for all commits conforming to the worktime format.
    """
    result = []
    for commit in commits:
        parts = _parse_taskname_workhours(commit.subject)
        if parts is None:  # this is no worktime commit
            continue
        taskname, worktime = parts  # unpack
        result.append(WorkEntry(commit, taskname, worktime))
    print(len(result), "worktime entry commits")
    return result


def student_work_so_far(course) -> tg.Tuple[list[ReportEntry], float, float]:
    """
    Data for work report: 
    retrieve pre-computed per-task entries (worktime, attempts) and totals (workhours, timevalue)
    from a Course object previously filled by compute_student_work_so_far().
    """
    workhours_total = 0.0
    timevalue_total = 0.0
    result = []
    for taskname in sorted((t.name for t in course.taskdict.values())):
        task = course.taskdict[taskname]
        if task.workhours != 0.0:
            workhours_total += task.workhours
            if task.is_accepted:
                timevalue_total += task.timevalue
            result.append(ReportEntry(taskname, task.path, task.workhours, task.timevalue,
                                      task.rejections, task.is_accepted))
    return result, workhours_total, timevalue_total


def is_accepted(tasknote: str):
    overridden = tasknote.startswith(c.SUBMISSION_OVERRIDE_PREFIX)
    if overridden:
        tasknote = tasknote[len(c.SUBMISSION_OVERRIDE_PREFIX):]
    return tasknote.startswith(c.SUBMISSION_ACCEPT_MARK)


def is_rejected(tasknote: str):
    overridden = tasknote.startswith(c.SUBMISSION_OVERRIDE_PREFIX)
    if overridden:
        tasknote = tasknote[len(c.SUBMISSION_OVERRIDE_PREFIX):]
    return tasknote.startswith(c.SUBMISSION_REJECT_MARK)


def submission_file_entries(entries: tg.Iterable[ReportEntry], rejected: list[str] = None, 
                            override: bool = False) -> dict[str, str]:
    """taskname -> CHECK_MARK  for each yet-to-be-accepted task with effort in any commit."""
    candidates = dict()
    for e in entries:
        if rejected is None:
            if not e.accepted:
                candidates[e.taskname] = c.SUBMISSION_CHECK_MARK
        else:
            if e.taskname in rejected:
                candidates[e.taskname] = (c.SUBMISSION_OVERRIDE_PREFIX if override else "") + c.SUBMISSION_REJECT_MARK
            elif e.accepted:
                candidates[e.taskname] = (c.SUBMISSION_OVERRIDE_PREFIX if override else "") + c.SUBMISSION_ACCEPT_MARK
            else:
                candidates[e.taskname] = c.SUBMISSION_CHECK_MARK
    return candidates


def _accumulate_timevalues_and_attempts(checked_entries: tg.Sequence[TaskCheckEntry],
                                        course: sdrl.course.Course):
    """Reflect the checked_entries data in the course data structure."""
    for check in checked_entries:
        b.debug(f"tuple: {check.commit.hash}, {check.taskname}, {check.tasknote}")
        task = course.task(check.taskname)
        overridden = check.tasknote.startswith(c.SUBMISSION_OVERRIDE_PREFIX)
        tasknote = check.tasknote[len(c.SUBMISSION_OVERRIDE_PREFIX):] if overridden else check.tasknote
        if tasknote.startswith(c.SUBMISSION_ACCEPT_MARK):
            if not task.remaining_attempts and not overridden:
                b.warning(f"Cannot accept task that has consumed its allowed attempts: {check.taskname}")
            else:
                if overridden and task.rejections:
                    task.rejections -= 1
                task.is_accepted = True
                b.debug(f"{check.taskname} accepted, {'' if overridden else 'not '} overridden")
        elif tasknote.startswith(c.SUBMISSION_REJECT_MARK):
            if not task.is_accepted or overridden:
                if overridden:
                    task.is_accepted = False
                task.rejections += 1
                b.debug(f"{check.taskname} rejected, {'' if overridden else 'not '} overridden")
        else:
            pass  # unmodified entry: instructor has not checked it


def _accumulate_student_workhours_per_task(commits: tg.Iterable[sgit.Commit], course: sdrl.course.Course):
    """Reflect the workentries data in the course data structure."""
    num_commits = num_timeentries = 0
    for commit in commits:
        num_commits += 1
        parts = _parse_taskname_workhours(commit.subject)
        if parts is None:  # this is no worktime commit
            continue
        taskname, worktime = parts  # unpack
        if taskname in course.taskdict:
            task = course.taskdict[taskname]
            task.workhours += worktime
            num_timeentries += 1
        else:
            b.warning(f"Commit '{commit.subject}': Task '{taskname}' does not exist. Entry ignored.")
    b.info(f"read {num_commits} commit messages, found {num_timeentries} work time entries")


def _parse_taskname_workhours(commit_msg: str) -> tg.Optional[tg.Tuple[str, float]]:  # taskname, workhours
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
