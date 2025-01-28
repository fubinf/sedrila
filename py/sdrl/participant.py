import collections
import contextlib
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
import git
import sdrl.constants as c
import sdrl.course
import sdrl.repo as r


_context: 'Context'  # global singleton, see make_context(), get_context()


class PathsAndRemaining(tg.NamedTuple):
    paths_matched: set[str]
    remaining_tasks: set[str]


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
    course_url: str  # SeDriLa homepage URL minus the '/index.html' part
    student_name: str
    student_id: str
    student_gituser: str
    partner_gituser: str

    def __init__(self, rootdir='.', with_submission=False):
        self.topdir = rootdir = rootdir.rstrip('/')
        if not os.path.exists(rootdir):
            b.critical(f"'{rootdir}' does not exist.")
        elif not os.path.isdir(rootdir):
            b.critical(f"'{rootdir}' must be a directory.")
        # ----- read c.PARTICIPANT_FILE:
        try:
            data = b.slurp_yaml(self.participantfile_path)
        except FileNotFoundError:
            b.critical(f"cannot read '{self.participantfile_path}'")
        # ----- interpret contents:
        try:
            self.course_url = str(data['course_url'])  # noqa
            self.student_name = str(data['student_name'])
            self.student_id = str(data['student_id'])
            self.student_gituser = str(data['student_gituser'])
            self.partner_gituser = str(data['partner_gituser'])
        except KeyError:
            b.critical(f"malformed file '{self.participantfile_path}': must contain strings " +
                       str([key for key in self.STUDENT_YAML_PROMPT_DEFAULTS]))
        homepage_explicitname = "index.html"
        if self.course_url.endswith(f"/{homepage_explicitname}"):
            self.course_url = self.course_url[:-len(homepage_explicitname)]  # leave only directory path
        if not self.course_url.endswith("/"):
            self.course_url += "/"  # make sure directory path ends with slash
        # ----- read c.SUBMISSION_FILE:
        if not with_submission or not os.path.isfile(self.submissionfile_path):
            self.submission = dict()
            return
        self.submission = b.slurp_yaml(self.submissionfile_path)
        self.filter_submission()
        if self.is_writable:
            self.save_submission()

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
        with contextlib.chdir(self.topdir):
            b.info(f"reading commit history in '{self.topdir}'")
            commits = git.commits_of_local_repo(reverse=True)
            r.compute_student_work_so_far(self.course, commits)
        return self.course

    @property
    def is_writable(self) -> bool:
        return True

    @property
    def participantfile_path(self) -> str:
        return os.path.join(self.topdir, c.PARTICIPANT_FILE)

    @functools.cached_property
    def pathset(self) -> set[str]:
        """file pathnames within root dir"""
        raw_pathlist = (str(p) for p in pathlib.Path(self.topdir).glob('**/*')
                        if '/.git/' not in str(p) and p.is_file())
        start = len(self.topdir)  # index after 'root/' in each path, except it includes the slash
        return set((p[start:] for p in raw_pathlist))

    @property
    def submissionfile_path(self) -> str:
        return os.path.join(self.topdir, c.SUBMISSION_FILE)

    @property
    def submission_backup_path(self) -> str:
        return os.path.join(self.topdir, '..', c.SUBMISSION_FILE)

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
        """regexp matching the name of any submitted task"""
        items_re = '|'.join([re.escape(item) for item in sorted(self.submission)])
        return re.compile(f"\\b{items_re}\\b")  # match task names only as words or multiwords

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
                paths_matched.add(p)
                submissions_matched.add(mm.group())
        remaining_submissions = set(self.submission_tasknames) - submissions_matched
        return PathsAndRemaining(paths_matched, remaining_submissions)

    def path_actualpath(self, path: str) -> str:
        """Turns the absolute virtual path into a physical path."""
        assert path[0] == '/'
        return os.path.join(self.topdir, path[1:])

    def path_actualsize(self, path: str) -> int:
        return pathlib.Path(self.path_actualpath(path)).stat().st_size

    def path_exists(self, path: str) -> bool:
        return path in self.pathset

    def filter_submission(self):
        """Kick out non-existing and rejected-for-good tasks and emit warnings."""
        submission1 = dict(**self.submission)  # constant copy (we will delete entries)
        file = self.submissionfile_path  # abbrev
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

    def save_submission(self):
        b.spit_yaml(self.submission_backup_path, self.submission)


class StudentS(Student):
    """
    Non-writable (wrt c.SUBMISSION_FILE) variant of Student.
    This class is used by student (hence the S in the name) and possibly viewer.
    """
    @property
    def is_writable(self) -> bool:
        return False

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


class Context:
    pargs: ap_sub.Namespace
    students: collections.OrderedDict[str, Student]
    studentlist: list[Student]
    is_instructor: bool

    def __init__(self, pargs: ap_sub.Namespace, dirs: list[str], student_class: type[Student], 
                 with_submission: bool, show_size: bool, is_instructor: bool):
        self.pargs = pargs
        self.students = collections.OrderedDict()
        self.is_instructor = is_instructor
        for workdir in dirs:
            self.students[workdir] = student = student_class(workdir, with_submission)
            if show_size:
                len_submissions = f"\t{len(student.submission)} submissions" if with_submission else ""
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
    def pathset(self) -> set[str]:
        """file pathnames present in any Workdir"""
        return set(itertools.chain.from_iterable((wd.pathset for wd in self.studentlist)))

    @functools.cached_property
    def submission(self) -> set[str]:
        """union of submitted tasknames"""
        return set(itertools.chain.from_iterable((wd.submission for wd in self.studentlist)))

    @functools.cached_property
    def submission_pathset(self) -> set[str]:
        """union of submission_pathsets"""
        return set(itertools.chain.from_iterable((wd.submission_pathset for wd in self.studentlist)))

    @functools.cached_property
    def submission_re(self) -> re.Pattern:
        """regexp matching the name of any submitted task"""
        items_re = '|'.join([re.escape(item) for item in sorted(self.submission)])
        return re.compile(f"\\b({items_re})\\b")  # match task names only as words or multiwords

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


def make_context(pargs: ap_sub.Namespace, dirs: list[str], student_class: type[Student], 
                 with_submission: bool, show_size=False, is_instructor=False):
    global _context
    _context = Context(pargs, dirs, student_class, with_submission, show_size, is_instructor)
    return _context


def get_context() -> Context:
    global _context
    return _context
