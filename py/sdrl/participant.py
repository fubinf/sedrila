import base as b

PARTICIPANT_FILE = "student.yaml"

class Student:
    def __init__(self):
        try:
            data = b.slurp_yaml(PARTICIPANT_FILE)
        except:
            b.critical(f"cannot read '{PARTICIPANT_FILE}'")
        try:
            self.course_url = data['course_url']
            assert isinstance(self.course_url, str)
            self.student_name = data['student_name']
            assert isinstance(self.student_name, str)
            self.student_id = str(data['student_id'])
            self.partner_student_name = data['partner_student_name']
            assert isinstance(self.partner_student_name, str)
            self.partner_student_id = str(data['partner_student_id'])
        except:
            b.critical(f"malformed file '{PARTICIPANT_FILE}': must contain "
                       "course_url, student_name, student_id, partner_student_name, partner_student_id.")
