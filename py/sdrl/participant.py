import contextlib
import functools
import json
import os

import requests

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.repo as r


class Student:
    """
    Represents the content of c.PARTICIPANT_FILE. Can initialize that file.
    Can represent and modify c.SUBMISSION_FILE.
    Modified versions are kept in {student_gituser}-{c.SUBMISSION_FILE} in superdir.
    """
    PROMPT_CONFIG_ATTR = 'student_yaml_attribute_prompts'
    STUDENT_YAML_PROMPT_DEFAULTS = dict(
        course_url="URL of course homepage: ",
        student_name="Your full name (givenname familyname): ",
        student_id="Your student ID: ",
        student_gituser="Your git account name (git username): ",
        partner_gituser="Your partner's git account name (or empty if you work alone): ",
    )
    root: str  # where PARTICIPANT_FILE lives
    course_url: str  # SeDriLa homepage URL minus the '/index.html' part
    student_name: str
    student_id: str
    student_gituser: str
    partner_gituser: str

    def __init__(self, rootdir='.', with_submission=False):
        self.root = rootdir = rootdir.rstrip('/')
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
        with contextlib.chdir(self.root):
            commits = git.commits_of_local_repo(reverse=True)
            r.compute_student_work_so_far(self.course, commits)
        return self.course

    @property
    def is_writable(self) -> bool:
        return True

    @property
    def participantfile_path(self) -> str:
        return os.path.join(self.root, c.PARTICIPANT_FILE)

    @property
    def submissionfile_path(self) -> str:
        return os.path.join(self.root, c.SUBMISSION_FILE)

    @property
    def submission_backup_path(self) -> str:
        return os.path.join(self.root, '..', c.SUBMISSION_FILE)

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


class StudentReadonly(Student):
    """
    Represents the content of c.PARTICIPANT_FILE. Can initialize that file.
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
