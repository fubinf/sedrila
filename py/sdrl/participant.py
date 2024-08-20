import functools
import json
import os

import requests

import base as b
import sdrl.constants as c


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
            if not os.path.isfile(c.PARTICIPANT_FILE) and os.path.isfile(os.path.join("..", c.PARTICIPANT_FILE)):
                self.root = ".."
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
            b.critical(f"malformed file '{c.PARTICIPANT_FILE}': must contain "
                       "course_url, student_name, student_id, partner_student_name, partner_student_id.")
        self.metadata_url = f"{self.course_url}/{c.METADATA_FILE}"

    @functools.cached_property
    def metadatadict(self) -> b.StrAnyDict:
        return self.get_metadata(self.course_url)
        
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

    @staticmethod
    def prompts(pdict):
        pdict.setdefault('student_name', "Name")
        pdict.setdefault('student_id', "ID")
        pdict.setdefault('partner_student_name', "Partner's name")
        pdict.setdefault('partner_student_id', "Partner's ID")
        return pdict
