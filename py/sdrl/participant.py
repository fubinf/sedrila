import os

import base as b

PARTICIPANT_FILE = "student.yaml"


class Student:
    def __init__(self):
        root = "."
        try:
            # grant students some slack. if they are calling from inside a working dir, it's fine.
            if not os.path.isfile(PARTICIPANT_FILE) and os.path.isfile(os.path.join("..", PARTICIPANT_FILE)):
                root = ".."
            data = b.slurp_yaml(os.path.join(root, PARTICIPANT_FILE))
        except FileNotFoundError:
            b.critical(f"cannot read '{PARTICIPANT_FILE}'")
        try:
            self.root = root
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

    @staticmethod
    def prompts(pdict):
        pdict.setdefault('student_name', "Name")
        pdict.setdefault('student_id', "ID")
        pdict.setdefault('partner_student_name', "Partner's name")
        pdict.setdefault('partner_student_id', "Partner's ID")
        return pdict
