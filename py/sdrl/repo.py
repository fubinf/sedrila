"""
Logic for handling information coming from git repos: 
effort commits, submissions, submission checks.
Knows about the respective format conventions.
"""
import re
import subprocess as sp
import typing as tg

import yaml

import base as b
import git
import sdrl.constants as c
import sdrl.course


class TaskCheckEntry(tg.NamedTuple):
    commit_id: str
    taskname: str
    tasknote: str


class ReportEntry(tg.NamedTuple):
    taskname: str
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


def compute_student_work_so_far(course: sdrl.course.Course, commits: tg.Sequence[git.Commit]):
    """
    Obtain per-task worktimes from student commits and 
    per-task timevalues from submission checked commits.
    Store them in course.
    """
    _accumulate_workhours_per_task(commits, course)
    instructor_commits = _submission_checked_commit_hashes(course, commits)
    taskcheck_entries = _taskcheck_entries_from_commits(instructor_commits, course)
    _accumulate_timevalues_and_attempts(taskcheck_entries, course)


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
            result.append(ReportEntry(taskname, task.workhours, task.timevalue,
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


def _accumulate_timevalues_and_attempts(checked_entries: tg.Sequence[tg.Sequence[TaskCheckEntry]],
                                        course: sdrl.course.Course):
    """Reflect the checked_entries data in the course data structure."""
    for checked_commit in checked_entries:
        for check in checked_commit:
            b.debug(f"tuple: {check.commit_id}, {check.taskname}, {check.tasknote}")
            task = course.task(check.taskname)
            requirements = {requirement: course.task(requirement) for requirement in task.requires
                            if course.task(requirement) is not None}  # ignore Taskgroups
            b.debug(f"requirements({task.name}): {requirements}")
            open_requirements = [taskname for taskname, task in requirements.items()
                                 if not(any(taskname == tname for (_, tname, _) in checked_commit)) and
                                 not task.is_accepted and task.remaining_attempts]
            if open_requirements:
                b.warning(f"Attempted to grade task {check.taskname} with missing requirements: {open_requirements}")
                continue
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


def _accumulate_workhours_per_task(commits: tg.Iterable[git.Commit], course: sdrl.course.Course):
    """Reflect the workentries data in the course data structure."""
    for commit in commits:
        parts = _parse_taskname_workhours(commit.subject)
        if parts is None:  # this is no worktime commit
            continue
        taskname, worktime = parts  # unpack
        if taskname in course.taskdict:
            task = course.taskdict[taskname]
            task.workhours += worktime
        else:
            b.warning(f"Commit '{commit.subject}': Task '{taskname}' does not exist. Entry ignored.")


def _taskcheck_entries_from_commits(instructor_commits: list[str], course: sdrl.course.Course
                                    ) -> tg.Sequence[tg.Sequence[TaskCheckEntry]]:
    """
    Collect the individual entries from each 'submission.yaml checked' commit (inner sequence of result)
    across all such commits (outer sequence), based on commit ids.
    """
    result = []
    for commit in instructor_commits:
        checks = yaml.safe_load(git.contents_of_file_version(commit, c.SUBMISSION_FILE, encoding='utf8'))
        group = [TaskCheckEntry(commit, taskname, tasknote) for taskname, tasknote in checks.items()]
        result.append(group)
    return result


def _submission_checked_commit_hashes(course: sdrl.course.Course,
                                      commits: tg.Sequence[git.Commit]) -> list[str]:
    """Commit id hashes of properly instructor-signed commits of finished submission checks."""
    try:
        allowed_signers = [b.as_fingerprint(instructor['keyfingerprint'])
                           for instructor in course.instructors]
    except KeyError:
        allowed_signers = []  # silence linter warning
        b.critical("missing 'keyfingerprint' in configuration")
    result = []
    for commit in commits:
        b.debug(f"commit.subject, fpr: {commit.subject}, {commit.key_fingerprint}")
        right_subject = re.match(c.SUBMISSION_CHECKED_COMMIT_MSG, commit.subject) is not None
        right_signer = commit.key_fingerprint and b.as_fingerprint(commit.key_fingerprint) in allowed_signers  
        if right_subject and right_signer:
            result.append(commit.hash)
    return result


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
