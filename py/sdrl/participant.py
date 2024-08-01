import os

import requests

import base as b

PARTICIPANT_FILE = "student.yaml"


class Student:
    root: str  # where PARTICIPANT_FILE lives: '.' or '..'
    course_url: str  # SeDriLa homepage URL minus the '/index.html' part
    student_name: str
    student_id: str
    partner_student_name: str
    partner_student_id: str
    metadata_url: str  # where to get JSON config

    def __init__(self):
        self.root = "."
        try:
            # grant students some slack. if they are calling from inside a working dir, it's fine.
            if not os.path.isfile(PARTICIPANT_FILE) and os.path.isfile(os.path.join("..", PARTICIPANT_FILE)):
                self.root = ".."
            data = b.slurp_yaml(os.path.join(self.root, PARTICIPANT_FILE))
        except FileNotFoundError:
            b.critical(f"cannot read '{PARTICIPANT_FILE}'")
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
            b.critical(f"malformed file '{PARTICIPANT_FILE}': must contain "
                       "course_url, student_name, student_id, partner_student_name, partner_student_id.")
        self.metadata_url = f"{self.course_url}/{b.METADATA_FILE}"

    @property
    def metadatadict(self) -> b.StrAnyDict:
        return self.get_metadata(self.course_url)
        
    @staticmethod    
    def get_metadata(course_url: str) -> b.StrAnyDict:
        url = os.path.join(course_url, b.METADATA_FILE)
        try:
            resp = requests.get(url=url)
        except:  # noqa
            b.critical(f"Error fetching URL '{url}'.")
        try:
            metadata = resp.json()
        except:  # noqa
            b.critical(f"JSON format error at '{url}'")
        return metadata

    @staticmethod
    def prompts(pdict):
        pdict.setdefault('student_name', "Name")
        pdict.setdefault('student_id', "ID")
        pdict.setdefault('partner_student_name', "Partner's name")
        pdict.setdefault('partner_student_id', "Partner's ID")
        return pdict
