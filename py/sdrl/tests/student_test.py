import sdrl.constants as c
import sdrl.repo as r
import sdrl.subcmd.student as s

import repo_test as rt


def test_student_work_so_far():
    def preparations():
        """make various fixed student commits and instructor commits"""
        rt.commit("%A 1h", 
                  "%B 1h"),
        rt.request_grading("A", 
                           "B")
        rt.grade({"A": c.SUBMISSION_REJECT_MARK})  # may or may not count double
        rt.grade({"A": c.SUBMISSION_REJECT_MARK, 
                  "B": c.SUBMISSION_REJECT_MARK})
        rt.commit("%A 1h", 
                  "%B 1h", 
                  "%Task1 1h", 
                  "%Task2 1h")
        rt.request_grading("A", 
                           "B")
        rt.grade({"A": c.SUBMISSION_ACCEPT_MARK, 
                  "B": c.SUBMISSION_CHECK_MARK}, 
              signed=False)  # we must ignore these grades so the student can't cheat
        # grading unrequested tasks should not be allowed
        rt.grade({"A": c.SUBMISSION_REJECT_MARK, 
                  "B": c.SUBMISSION_REJECT_MARK, 
                  "Task1": c.SUBMISSION_REJECT_MARK, 
                  "Task2": c.SUBMISSION_ACCEPT_MARK})
        rt.commit("%A 1h", 
                  "%B 1h")
        rt.request_grading("A", 
                           "B")
        rt.grade({"A": c.SUBMISSION_REJECT_MARK, 
                  "B": c.SUBMISSION_ACCEPT_MARK})
        rt.request_grading("A")
        # accepting tasks over the rejection limit should not be allowed
        rt.grade({"A": c.SUBMISSION_ACCEPT_MARK})

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1 + 1.0/h"

    def assertions(course):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (course.task(e[0]).remaining_attempts, *e[2:]) for e in entries}
        # (open rejections, workhours, timevalue, rejections, accepted)
        assert entrymap["A"] == (0, 3.0, 1.0, 4, False)  # last accept commit didn't count: it was over rejection limit
        assert entrymap["B"] == (1, 3.0, 2.5, 2, True)
        assert entrymap["Task1"] == (1, 1.0, 1.0, 1, False)  # rejection counted although not requested
        assert entrymap["Task2"] == (3, 1.0, 2.0, 0, True)  # acceptance counted although not requested
        table = []
        s.report_student_work_so_far(course, entries, workhours_total, timevalue_total, table)
        assert ("A", "3.00", "1.00", f"{c.SUBMISSION_REJECT_MARK} (after 2 attempts)") in table
        assert ("B", "3.00", "2.50", f"{c.INTERACT_ACCEPT_SYMBOL} {c.INTERACT_REJECT_SYMBOL*2}") in table
        assert ("Task1", "1.00", "1.00", "X (1 of 2 remain)") in table
        assert ("Task2", "1.00", "2.00", "✓ ") in table

    rt.run_inside_repo(preparations, assertions, coursemodifications)


def test_submitting_requirement():
    def preparations():
        # make tallying of time happy with at least one commit per task
        rt.commit("%A 1h", 
                  "%requiresA 1h", 
                  "%requiresRequiresA 1h", 
                  "%B 1h", 
                  "%requiresB 1h")
        rt.request_grading("A", "requiresB")
        rt.grade({"A": c.SUBMISSION_ACCEPT_MARK})
        rt.request_grading("requiresRequiresA", 
                           "requiresA", 
                           "B")  # accepting both at once should work!
        rt.grade({"requiresA": c.SUBMISSION_ACCEPT_MARK, 
                  "requiresRequiresA": c.SUBMISSION_ACCEPT_MARK, 
                  "B": c.SUBMISSION_REJECT_MARK})
        rt.request_grading("requiresB")
        # we have rejected B completely, but students should now be allowed to do requiresB
        rt.grade({"requiresB": c.SUBMISSION_ACCEPT_MARK})

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def assertions(course):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (course.task(e[0]).remaining_attempts, *e[4:]) for e in entries}
        # (open rejections, rejections, accepted)
        assert entrymap["A"] == (1, 0, True)
        assert entrymap["requiresA"] == (1, 0, True)
        assert entrymap["requiresRequiresA"] == (1, 0, True)
        assert entrymap["B"] == (0, 1, False)
        assert entrymap["requiresB"] == (1, 0, True)

    rt.run_inside_repo(preparations, assertions, coursemodifications)


def test_grading_mistakes():
    def preparations(override):
        """make various fixed student commits and instructor commits"""
        rt.commit("%A 1h", 
                  "%B 1h"),
        rt.request_grading("A", 
                           "B")
        rt.grade({"A": c.SUBMISSION_REJECT_MARK, 
                  "B": c.SUBMISSION_ACCEPT_MARK})  # initial false gradings
        rt.request_grading("A", 
                           "B")
        rt.grade({"A": (c.SUBMISSION_OVERRIDE_PREFIX if override else "") + c.SUBMISSION_ACCEPT_MARK, 
                  "B": (c.SUBMISSION_OVERRIDE_PREFIX if override else "") + c.SUBMISSION_REJECT_MARK})  # attempted fix

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def assertions(course, override):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e.taskname: (course.task(e.taskname).remaining_attempts, *e[4:]) for e in entries}
        # taskname -> (open rejections, rejections, accepted)
        # we either expect _only_ the first or _only_ the second option to be present
        assert entrymap["B" if override else "A"] == (0, 1, False)
        assert entrymap["A" if override else "B"] == (1, 0, True)

    rt.run_inside_repo(lambda: preparations(False), lambda course: assertions(course, False), 
                       coursemodifications)
    rt.run_inside_repo(lambda: preparations(True), lambda course: assertions(course, True), 
                       coursemodifications)
