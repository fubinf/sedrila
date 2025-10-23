import collections
import contextlib
import enum
import functools
import itertools
import json
import os
import pathlib
import re
import typing as tg

import argparse_subcommand as ap_sub
import requests

import base as b
import sgit
import sdrl.constants as c
import sdrl.course
import sdrl.repo as r


_context: 'Context'  # global singleton, see make_context(), get_context()


class PathsAndRemaining(tg.NamedTuple):
    paths_matched: set[str]
    remaining_tasks: set[str]

class SubmissionTaskState(enum.StrEnum):
    """
    used by SubmissionTask
    the extended state of a submitted task
    also taskes into account things like final rejects
    and distinguishes between current and past rejects
    """
    # the task name is invalid
    INVALID = "INVALID"

    # task marked as check
    CHECK = "CHECK"
    # task marked as accept
    ACCEPT = "ACCEPT"
    # task marked as reject
    REJECT = "REJECT"

    # the task was accepted by the instructor in the past
    ACCEPT_PAST = "ACCEPT_PAST"
    # the task was rejected the maximum amount of times permitted
    REJECT_FINAL = "REJECT_FINAL"

class SubmissionTask:
    """
    stores the set of files submitted for a task
    as the names do not have to match up with the task
    anymore like in old builds of sedrila

    also contains the precise state of the task for display and editing
    """
    # set of (relative) file paths that are part of the task
    files: set[str]
    # current state of the task, None if the 
    # task is not considered in any way
    # (equivalent of NONCHECK in the past)
    state: SubmissionTaskState | None = None

    def __init__(self): self.files = set()

    # true if the task was registered
    # via a commit / submission.yaml
    @property
    def is_registered(self) -> bool: return self.state is not None

    @property
    def is_checkable(self) -> bool:
        """returns wether the task can be marked for submission or checked"""
        valid = [None, SubmissionTaskState.CHECK, SubmissionTaskState.ACCEPT, SubmissionTaskState.REJECT]
        return self.state in valid

    @property
    def is_student_checkable(self) -> bool:
        valid = [None, SubmissionTaskState.CHECK, SubmissionTaskState.REJECT]
        return self.state in valid

class Submission:
    """
    contains data about an entire submission of a student (processed tasks)
    and allows to query them in various ways
    """
    # the set of tasks that have a commit
    _tasks: tg.Dict[str, SubmissionTask]

    def __init__(self): self._tasks = {}

    def _get_or_add_empty(self, name: str) -> SubmissionTask:
        self._add_empty_task(name)
        return self._tasks[name]

    def _add_empty_task(self, name: str):
        if name not in self._tasks: self._tasks[name] = SubmissionTask()

    def _add_task_file(self, name: str, path: str):
        self._add_empty_task(name)
        self._tasks[name].files.add(path)

    def _remove_if_empty(self, name: str):
        task = self._tasks.get(name)
        if not task: return
        del self._tasks[name]

    def task(self, name: str) -> SubmissionTask | None: return self._tasks.get(name)

    @functools.cached_property
    def _task_items(self) -> tg.Iterable[tuple[str, SubmissionTask]]:
        return sorted(self._tasks.items())

    @property
    def candidates(self) -> tg.Iterable[tuple[str, SubmissionTask]]:
        return filter(lambda t: not t[1].is_registered, self._task_items)

    @property
    def to_check(self) -> tg.Iterable[tuple[str, SubmissionTask]]:
        return filter(lambda t: t[1].state == SubmissionTaskState.CHECK, self._task_items)

    @property
    def accepted(self) -> tg.Iterable[tuple[str, SubmissionTask]]:
        return filter(lambda t: t[1].state == SubmissionTaskState.ACCEPT, self._task_items)

    @property
    def rejected(self) -> tg.Iterable[tuple[str, SubmissionTask]]:
        return filter(lambda t: t[1].state == SubmissionTaskState.REJECT, self._task_items)

    @property
    def submission_yaml(self) -> tg.Iterable[tuple[str, str]]:
        return (
            (name, str(t.state) if t.state else c.SUBMISSION_NONCHECK_MARK)
            for name, t
            in itertools.chain(self.to_check, self.accepted, self.rejected)
        )



class Student:
    """
    Represents the content of c.PARTICIPANT_FILE. Can initialize that file.
    Represents the content of the student's working directory tree.
    Can represent and modify c.SUBMISSION_FILE.
    Modified versions are kept in {student_gituser}-{c.SUBMISSION_FILE} in superdir.
    This class is used by instructor.
    """
    PROMPT_CONFIG_ATTR = 'student_yaml_attribute_prompts'
    STUDENT_YAML_PROMPT_DEFAULTS = dict(
        course_url="URL of course homepage: ",
        student_name="Your full name (givenname familyname): ",
        student_id="Your student ID: ",
        student_gituser="Your git account name (git username): ",
        partner_gituser="Your partner's git account name (or empty if you work alone): ",
    )
    topdir: str  # where PARTICIPANT_FILE lives
    is_instructor: bool
    possible_submission_states = list[str]
    course_url: str  # SeDriLa homepage URL minus the '/index.html' part
    student_name: str
    student_id: str
    student_gituser: str
    partner_gituser: str

    def __init__(self, rootdir: str, is_instructor: bool):
        self.topdir = rootdir = rootdir.rstrip('/')
        self.is_instructor = is_instructor
        if is_instructor:
            self.possible_submission_states = [c.SUBMISSION_CHECK_MARK, 
                                               c.SUBMISSION_ACCEPT_MARK, c.SUBMISSION_REJECT_MARK]
        else:
            self.possible_submission_states = [c.SUBMISSION_NONCHECK_MARK, c.SUBMISSION_CHECK_MARK]
        if not os.path.exists(rootdir):
            b.critical(f"'{rootdir}' does not exist.")
        elif not os.path.isdir(rootdir):
            b.critical(f"'{rootdir}' must be a directory.")
        # ----- read c.PARTICIPANT_FILE:
        if not os.path.isfile(self.participantfile_path):
            b.critical(f"'{self.participantfile_path}' is missing. Have you called sedrila student --init?")
        data = b.slurp_yaml(self.participantfile_path)
        b.validate_dict_unsurprisingness(self.participantfile_path, data)
        # ----- interpret contents:
        try:
            self.course_url = str(data['course_url'])  # noqa
            self.student_name = str(data['student_name'])
            self.student_id = str(data['student_id'])
            self.student_gituser = str(data['student_gituser'])
            self.partner_gituser = str(data['partner_gituser'] or "")
        except KeyError:
            b.critical(f"malformed file '{self.participantfile_path}': must contain strings " +
                       str([key for key in self.STUDENT_YAML_PROMPT_DEFAULTS]))
        homepage_explicitname = "index.html"
        if self.course_url.endswith(f"/{homepage_explicitname}"):
            self.course_url = self.course_url[:-len(homepage_explicitname)]  # leave only directory path
        if not self.course_url.endswith("/"):
            self.course_url += "/"  # make sure directory path ends with slash
        # ----- read c.SUBMISSION_FILE:
        if not os.path.isfile(self.submissionfile_path):
            self.submission = dict()
        else:
            self.submission = b.slurp_yaml(self.submissionfile_path)
            b.validate_dict_unsurprisingness(self.submissionfile_path, self.submission)
        self.filter_submission()

    @functools.cached_property
    def course(self) -> sdrl.course.CourseSI:
        return sdrl.course.CourseSI(configdict=self.course_metadata, context=self.course_metadata_url)

    @functools.cached_property
    def course_metadata(self) -> b.StrAnyDict:
        return self.get_course_metadata(self.course_url)

    @property
    def course_metadata_url(self) -> str:
        return self.get_course_metadata_url(self.course_url)

    @functools.cached_property
    def course_with_work(self) -> sdrl.course.CourseSI:
        """Set task.is_accepted and task.rejections values in course."""
        with contextlib.chdir(self.topdir):
            b.info(f"'{self.topdir}':\t reading commit history")
            commits = sgit.commits_of_local_repo(chronological=True)
            r.compute_student_work_so_far(self.course, commits)
        return self.course

    @property
    def is_participant(self) -> bool:
        return True  # TODO 1: implement instructor-side use of participantslist
        pid = getattr(self, self.participant_attrname)
        return pid in self.participantslist if pid else True  # an absent participantslist contains everybody

    @property
    def participant_attrname(self) -> str | None:
        p = self.course.configdict.get('participant', None)
        return p['student_attribute'] if p else None

    @property
    def participantslist(self) -> list[str]:
        rawlist = requests.get
        return ...

    @property
    def participantslist_url(self) -> set[str]:
        return f"{self.course_url}/instructor/{c.PARTICIPANTSLIST_FILE}"

    @property
    def participantfile_path(self) -> str:
        return os.path.join(self.topdir, c.PARTICIPANT_FILE)

    @functools.cached_property
    def pathset(self) -> set[str]:
        """file pathnames within topdir"""
        if self.topdir == '.':
            # pathlib.Path.glob() optimizes './' away, hence we need two versions of the logic
            raw_pathlist = (str(p) for p in pathlib.Path('.').glob('**/*')
                            if not str(p).startswith('.git/') and p.is_file())
            return {f"/{path}" for path in raw_pathlist}
        raw_pathlist = (str(p) for p in pathlib.Path(self.topdir).glob('**/*')
                        if '/.git/' not in str(p) and p.is_file())
        slashpos = len(self.topdir)  # index after topdir in each path
        return set((p[slashpos:] for p in raw_pathlist))

    @property
    def submissionfile_path(self) -> str:
        return os.path.join(self.topdir, c.SUBMISSION_FILE)

    @functools.cached_property
    def submissions(self) -> Submission:
        sub = Submission()

        for taskname, task in self.course_with_work.taskdict.items():
            sub._add_empty_task(taskname)
            for p in filter(lambda p: taskname in p, self.pathset):
                if p.endswith(f".{c.PATHSET_FILE_EXT}"):
                    for sp in self._extract_meta_files(p):
                        sub._add_task_file(taskname, sp)
                # add everything else
                else: sub._add_task_file(taskname, p)
                
            if (task.workhours <= 0
                and not task.is_accepted
                and not task.allowed_attempts <= 0
                and not taskname in self.submission):
                sub._remove_if_empty(taskname)

        # assign states to tasks from submission yaml
        for name, state in self.submission.items():
            task = sub._get_or_add_empty(name)
            if state == c.SUBMISSION_ACCEPT_MARK: task.state = SubmissionTaskState.ACCEPT
            elif state == c.SUBMISSION_REJECT_MARK: task.state = SubmissionTaskState.REJECT
            elif state == c.SUBMISSION_CHECK_MARK: task.state = SubmissionTaskState.CHECK
            # noncheck is the default state
            # all tasks are implicitly noncheck
            elif state == c.SUBMISSION_NONCHECK_MARK: task.state = None

        # assign states to tasks from commits
        cw = self.course_with_work
        for name, task in sub._tasks.items():
            cw_task = cw.task(name)
            if not cw_task: task.state = SubmissionTaskState.INVALID
            elif cw_task.remaining_attempts < 0: task.state = SubmissionTaskState.REJECT_FINAL
            elif cw_task.is_accepted: task.state = SubmissionTaskState.ACCEPT_PAST

        return sub


    @functools.cached_property
    def submission_pathset(self) -> set[str]:
        """paths with names matching submitted tasks"""
        return self._submission_pathset_and_remaining_submissions.paths_matched

    @functools.cached_property
    def submission_tasknames(self) -> set[str]:
        """tasknames from c.SUBMISSION_FILE (or empty if none)"""
        return set(self.submission.keys())

    @functools.cached_property
    def submission_re(self) -> re.Pattern:
        return _submission_re(self)

    @functools.cached_property
    def submissions_remaining(self) -> set[str]:
        """submissions not matched by paths"""
        return self._submission_pathset_and_remaining_submissions.remaining_tasks

    @functools.cached_property
    def _submission_pathset_and_remaining_submissions(self) -> PathsAndRemaining:
        """paths with names matching submitted tasks & this"""
        paths_matched, submissions_matched = set(), set()
        for p in self.pathset:
            mm = self.submission_re.search(p)
            if mm:
                if p.endswith(f".{c.PATHSET_FILE_EXT}"):
                    paths_matched.update(self._extract_meta_files(p))
                else: paths_matched.add(p)

                submissions_matched.add(mm.group())
        remaining_submissions = set(self.submission_tasknames) - submissions_matched
        return PathsAndRemaining(paths_matched, remaining_submissions)

    def _extract_meta_files(self, path: str) -> set[str]:
        """get all referenced file paths from a '.files' meta file"""
        full_path = self.path_actualpath(path)

        # got this from html_for_file
        contents = b.slurp(full_path)

        # as of now the file is keept quite simple:
        # add paths with a nonempty line containing the path,
        # relative to the directory the meta file is in
        # '#' to comment
        # no fancy patterns yet (but could be added easily)
        paths = {
            os.path.normpath(os.path.join("/", path, "../", p))
            for p in map(str.strip, contents.splitlines())
            if p != "" and not p.startswith("#")
        }
        files = set()
        for p in paths: files.add(p)

        return files
    


    def path_actualpath(self, path: str) -> str:
        """Turns the absolute virtual path into a physical path."""
        assert path[0] == '/'
        return os.path.join(self.topdir, path[1:])

    def path_actualsize(self, path: str) -> int:
        return pathlib.Path(self.path_actualpath(path)).stat().st_size

    def path_exists(self, path: str) -> bool:
        return path in self.pathset

    @classmethod
    def build_participant_file(cls):
        b.info(f"Your following inputs will populate the file '{c.PARTICIPANT_FILE}'.")
        # --- obtain course metadata:
        course_url = os.path.dirname(input("Course URL: "))
        course = Student.get_course_metadata(course_url)
        # --- obtain prompts for all further attributes:
        prompts = course.get(cls.PROMPT_CONFIG_ATTR, {})  # noqa
        for key, prompt in cls.STUDENT_YAML_PROMPT_DEFAULTS.items():
            if key not in prompts and key != "course_url":
                prompts[key] = prompt
        participant_data = dict(course_url=course_url)
        for value in prompts:
            participant_data[value] = input(prompts[value])
        b.spit_yaml(c.PARTICIPANT_FILE, participant_data)
        b.info(f"Wrote '{c.PARTICIPANT_FILE}'.")
        b.info("If you made any mistake, correct it with an editor now.")
        b.info("Then commit the file and push the commit.")

    def filter_submission(self):
        """Kick out non-existing and rejected-for-good tasks and emit warnings."""
        submission1 = dict(**self.submission)  # constant copy (we will delete entries)
        file = self.submissionfile_path  # abbrev
        dummy = self.course_with_work  # make sure we read the worktimes from repo. TODO 2: ugly!
        for taskname, status in submission1.items():
            task = self.course_with_work.task(taskname)
            if not task:
                b.warning(f"{file}: '{taskname}' is not a taskname. Ignored.")
                del self.submission[taskname]
            elif task.remaining_attempts < 0:
                b.warning(f"{file}: '{taskname}' has remaining_attempts = {task.remaining_attempts}. Ignored.")
                del self.submission[taskname]

    @classmethod
    def get_course_metadata(cls, course_url: str) -> b.StrAnyDict:
        FILE_URL_PREFIX = 'file://'
        url = cls.get_course_metadata_url(course_url)
        try:
            if url.startswith(FILE_URL_PREFIX):
                jsontext = b.slurp(url[len(FILE_URL_PREFIX):])
            else:
                jsontext = requests.get(url=url).text
        except Exception as exc:  # noqa
            jsontext = ""
            b.critical(f"Error fetching URL '{url}'.")
        try:
            metadata = json.loads(jsontext)
        except:  # noqa
            metadata = dict()
            b.critical(f"JSON format error at '{url}'")
        return metadata

    @classmethod    
    def get_course_metadata_url(cls, course_url: str) -> str:
        return os.path.join(course_url, c.METADATA_FILE)

    @classmethod    
    def get_course_url(cls, student_file: str) -> str:
        student_metadata = b.slurp_yaml(student_file)
        return student_metadata['course_url']

    def set_state(self, taskname: str, new_state: SubmissionTaskState) -> bool:
        task = self.submissions.task(taskname)
        if not task: return False
        task.state = new_state if new_state != c.SUBMISSION_NONCHECK_MARK else None
        if taskname in self.submission: self.submission[taskname] = new_state
        self.save_submission()
        return True

    def save_submission(self):
        """Write self.submission to c.SUBMISSION_FILE"""
        b.spit_yaml(self.submissionfile_path, dict(self.submissions.submission_yaml))

    def submission_find_taskname(self, path: str) -> str:
        return _submission_find_taskname(self, path)


class Context:
    # TODO 2: add cached_property is_gpg_available()
    pargs: ap_sub.Namespace
    students: collections.OrderedDict[str, Student]
    studentlist: list[Student]
    is_instructor: bool

    def __init__(self, pargs: ap_sub.Namespace, dirs: list[str], 
                 is_instructor: bool, show_size: bool):
        self.pargs = pargs
        self.students = collections.OrderedDict()
        self.is_instructor = is_instructor
        for workdir in dirs:
            self.students[workdir] = student = Student(workdir, is_instructor)
            if show_size:
                len_submissions = f"\t{len(student.submission)} submissions" if student.submission else ""
                b.info(f"'{student.topdir}':\t{len(student.pathset)} files{len_submissions}")
        self.studentlist = list(self.students.values())
        course_urls_set = {s.course_url for s in self.students.values()}
        if len(course_urls_set) > 1:
            b.critical(f"All work dirs must come from the same course. I found several: {course_urls_set}")

    @property
    def course(self) -> sdrl.course.Course:
        return self.studentlist[0].course

    @property
    def course_url(self) -> str:
        return self.studentlist[0].course_url

    @functools.cached_property
    def tasknames(self) -> set[str]:
        return set(itertools.chain(*(
            s.submissions._tasks.keys() for s in self.studentlist
        )))

    @functools.cached_property
    def pathset(self) -> set[str]:
        """file pathnames present in any Workdir"""
        return set(itertools.chain.from_iterable((wd.pathset for wd in self.studentlist)))

    @functools.cached_property
    def submission_tasknames(self) -> set[str]:
        """union of submitted tasknames"""
        return set(itertools.chain.from_iterable((wd.submission_tasknames for wd in self.studentlist)))

    @functools.cached_property
    def submission_pathset(self) -> set[str]:
        """union of submission_pathsets"""
        return set(itertools.chain.from_iterable((wd.submission_pathset for wd in self.studentlist)))

    @functools.cached_property
    def submission_re(self) -> re.Pattern:
        return _submission_re(self)

    @functools.cached_property
    def submissions_remaining(self) -> set[str]:
        """submissions not matched (in at least one Workdir) by paths"""
        return set(itertools.chain.from_iterable((wd.submissions_remaining for wd in self.studentlist)))

    def ls(self, dirname: str) -> tuple[set[str], set[str]]:
        """dirs, files = ls("/some/dir/")  somewhat like the Unix ls command"""
        assert dirname.endswith('/')
        dirs, files = set(), set()
        start = len(dirname)  # index of 'local' (within dirname) part of pathname
        for path in self.pathset:
            if not path.startswith(dirname):  # not our business
                continue
            localpath = path[start:]
            slashpos = localpath.find("/")
            slash_found = slashpos > -1
            if slash_found:
                dirs.add(localpath[:slashpos + 1])  # adding it again makes no difference
            else:
                files.add(localpath)
        return dirs, files

    def submission_find_taskname(self, path: str) -> str:
        return _submission_find_taskname(self, path)


def make_context(pargs: ap_sub.Namespace, dirs: list[str], *, is_instructor: bool, 
                 show_size=False):
    global _context
    _context = Context(pargs, dirs, is_instructor=is_instructor, show_size=show_size)
    return _context


def get_context() -> Context:
    global _context
    return _context


def _submission_find_taskname(studentoid, path: str) -> str:
    """Return longest taskname found in path or '' if none is found."""
    mm = studentoid.submission_re.search(path)
    return mm.group() if mm else ""


def _submission_re(studentoid) -> re.Pattern:
    """regexp matching the name of any submitted task for a Context or Student."""
    longest_first = sorted(sorted(studentoid.submission_tasknames), key=len, reverse=True)  # decreasing specificity
    items_re = '|'.join([re.escape(item) for item in longest_first])  # noqa, item has the right type
    return re.compile(f"\\b({items_re})\\b")  # match task names only as words or multiwords

