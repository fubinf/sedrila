import sdrl.repo as r
import sdrl.interactive as i
import sdrl.subcmd.student as s

from repo_test import commit, request_grading, grade, run_inside_repo

def test_student_work_so_far():
    def preparations():
        """make various fixed student commits and instructor commits"""
        commit("%A 1h", "%B 1h"),
        request_grading("A", "B")
        grade({"A": r.REJECT_MARK}) #should not count double
        grade({"A": r.REJECT_MARK, "B": r.REJECT_MARK})
        commit("%A 1h", "%B 1h", "%Task1 1h", "%Task2 1h")
        request_grading("A", "B")
        grade({"A": r.ACCEPT_MARK, "B": r.CHECK_MARK}, signed=False) #student can't cheat
        #grading unrequested tasks should not be allowed
        grade({"A": r.REJECT_MARK, "B": r.REJECT_MARK, "Task1": r.REJECT_MARK, "Task2": r.ACCEPT_MARK})
        commit("%A 1h", "%B 1h")
        request_grading("A", "B")
        grade({"A": r.REJECT_MARK, "B": r.ACCEPT_MARK})
        request_grading("A")
        #accepting tasks over the rejection limit should not be allowed
        grade({"A": r.ACCEPT_MARK})

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1 + 1.0/h"

    def assertions(course):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (course.task(e[0]).remaining_attempts, *e[1:]) for e in entries}
        # (open rejections, invested hours, task hours, rejections, accepted)
        assert entrymap["A"] == (0, 3.0, 1.0, 3, False)  # last accept commit didn't count: it was over rejection limit
        assert entrymap["B"] == (1, 3.0, 2.5, 2, True)
        assert entrymap["Task1"] == (2, 1.0, 1.0, 0, False)  # rejection not counted because it wasn't requested
        assert entrymap["Task2"] == (3, 1.0, 2.0, 0, False)  # acceptance not counted because it wasn't requested
        table = []
        s.report_student_work_so_far(course, entries, workhours_total, timevalue_total, table)
        assert ("A", "3.00", "1.00", f"{r.REJECT_MARK} (after 2 attempts)") in table
        assert ("B", "3.00", "2.50", f"{i.ACCEPT_SYMBOL} {i.REJECT_SYMBOL*2}") in table
        assert ("Task1", "1.00", "1.00", "") in table
        assert ("Task2", "1.00", "2.00", "") in table

    run_inside_repo(preparations, assertions, coursemodifications)

def test_submitting_requirement():
    def preparations():
        #make tallying of time happy with at least one commit per task
        commit("%A 1h", "%requiresA 1h", "%requiresRequiresA 1h", "%B 1h", "%requiresB 1h")
        request_grading("A", "requiresB")
        grade({"A": r.ACCEPT_MARK, "requiresB": r.REJECT_MARK}) #the later should not count, as B isn't done yet
        request_grading("requiresRequiresA", "requiresA", "B") #accepting both at once should work!
        grade({"requiresA": r.ACCEPT_MARK, "requiresRequiresA": r.ACCEPT_MARK, "B": r.REJECT_MARK})
        request_grading("requiresB")
        #now that we have rejected B completely, students should be allowed to du requiresB, just with more work attached
        grade({"requiresB": r.ACCEPT_MARK})

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def assertions(course):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (course.task(e[0]).remaining_attempts, *e[3:]) for e in entries}
        # (open rejections, rejections, accepted)
        assert entrymap["A"] == (1, 0, True)
        assert entrymap["requiresA"] == (1, 0, True)
        assert entrymap["requiresRequiresA"] == (1, 0, True)
        assert entrymap["B"] == (0, 1, False)
        assert entrymap["requiresB"] == (1, 0, True)

    run_inside_repo(preparations, assertions, coursemodifications)

def test_grading_mistakes():
    def preparations(override):
        """make various fixed student commits and instructor commits"""
        commit("%A 1h", "%B 1h"),
        request_grading("A", "B")
        grade({"A": r.REJECT_MARK, "B": r.ACCEPT_MARK}) #initial false gradings
        request_grading("A", "B")
        grade({"A": (r.OVERRIDE_PREFIX if override else "") + r.ACCEPT_MARK, "B": (r.OVERRIDE_PREFIX if override else "") + r.REJECT_MARK}) #attempted fix

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def assertions(course, override):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (course.task(e[0]).remaining_attempts, *e[3:]) for e in entries}
        # (open rejections, rejections, accepted)
        #we either expect _only_ the first or _only_ the second option to be present
        assert entrymap["B" if override else "A"] == (0, 1, False)
        assert entrymap["A" if override else "B"] == (1, 0, True)


    run_inside_repo(lambda: preparations(False), lambda course: assertions(course, False), coursemodifications)
    run_inside_repo(lambda: preparations(True), lambda course: assertions(course, True), coursemodifications)
