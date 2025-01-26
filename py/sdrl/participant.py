import functools
import json
import os

import requests

import base as b
import sdrl.constants as c


class Student:
    PROMPT_CONFIG_ATTR = 'student_yaml_attribute_prompts'
    root: str  # where PARTICIPANT_FILE lives
    course_url: str  # SeDriLa homepage URL minus the '/index.html' part
    student_name: str
    student_id: str
    student_gituser: str
    partner_gituser: str
    metadata_url: str  # where to get JSON config
    student_yaml_prompt_defaults = dict(
        course_url="URL of course homepage: ",
        student_name="Your full name (givenname familyname): ",
        student_id="Your student ID: ",
        student_gituser="Your git account name (git username): ",
        partner_gituser="Your partner's git account name (or empty if you work alone): ",
    )

    def __init__(self, rootdir='.'):
        self.root = rootdir
        try:
            self._adjust_root()
            data = b.slurp_yaml(os.path.join(self.root, c.PARTICIPANT_FILE))
        except FileNotFoundError:
            b.critical(f"cannot read '{c.PARTICIPANT_FILE}'")
        try:
            self.course_url = data['course_url']  # noqa
            assert isinstance(self.course_url, str)
            self.student_name = data['student_name']
            assert isinstance(self.student_name, str)
            self.student_id = str(data['student_id'])
            self.partner_student_name = data['partner_student_name']
            assert isinstance(self.partner_student_name, str)
            self.partner_student_id = str(data['partner_student_id'])
        except KeyError:
            b.critical(f"malformed file '{c.PARTICIPANT_FILE}': must contain strings "
                       "course_url, student_name, student_id, partner_student_name, partner_student_id.")
        homepage_explicitname = "index.html"
        if self.course_url.endswith(f"/{homepage_explicitname}"):
            self.course_url = self.course_url[:-len(homepage_explicitname)]  # leave only directory path
        if not self.course_url.endswith("/"):
            self.course_url += "/"  # make sure directory path ends with slash
        self.metadata_url = f"{self.course_url}{c.METADATA_FILE}"

    @functools.cached_property
    def metadatadict(self) -> b.StrAnyDict:
        return self.get_metadata(self.course_url)
    
    @property
    def participantfile_path(self) -> str:
        return os.path.join(self.root, c.PARTICIPANT_FILE)
    
    @staticmethod
    def dummy_participant() -> 'Student':
        """Pseudo-Student with no root and no course_url/metadata_url."""
        result = Student()
        result.student_name = "N.N."
        result.student_id = "some_id"
        result.partner_student_name = "-"
        result.partner_student_id = "-"
        return result

    @staticmethod    
    def get_metadata(course_url: str) -> b.StrAnyDict:
        FILE_URL_PREFIX = 'file://'
        url = os.path.join(course_url, c.METADATA_FILE)
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
    def build_participant_file(cls):
        b.info(f"Your following inputs will populate the file '{c.PARTICIPANT_FILE}'.")
        # --- obtain course metadata:
        course_url = os.path.dirname(input("Course URL: "))
        course = Student.get_course_metadata(course_url)
        # --- obtain prompts for all further attributes:
        prompts = course.get(cls.PROMPT_CONFIG_ATTR, {})  # noqa
        for key, prompt in cls.student_yaml_prompt_defaults.items():
            if key not in prompts:
                prompts[key] = prompt
        participant_data = dict(course_url=course_url)
        for value in prompts:
            participant_data[value] = input(prompts[value])
        b.spit_yaml(c.PARTICIPANT_FILE, participant_data)
        b.info(f"Wrote '{c.PARTICIPANT_FILE}'.")
        b.info("If you made any mistake, correct it with an editor now.")
        b.info("Then commit the file and push the commit.")

    def _adjust_root(self):
        # grant students some slack. if they are calling from inside a working dir, it's fine.
        participantfile_found = os.path.isfile(self.participantfile_path)
        root_is_relative_path = not os.path.isabs(self.root)
        participantfile_found_one_level_higher = os.path.isfile(os.path.join('..', self.participantfile_path))
        if not participantfile_found and root_is_relative_path and participantfile_found_one_level_higher:
            self.root = ".."  # use PARTICIPANT_FILE from superdir
