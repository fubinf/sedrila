import sdrl.repo as r
import sdrl.interactive as i
import sdrl.subcmd.student as s

from repo_test import commit, request_grading, grade, run_inside_repo

def test_student_work_so_far():
    def preparations():
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
        course_json["rejection_allowance"] = "1+1/h"

    def assertions(course):
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        entrymap = {e[0]: (*course.task(e[0]).open_rejections(), *e[1:]) for e in entries}
        #(open rejections, rejections overused, invested hours, task hours, rejections, accepted)
        assert entrymap["A"] == (0, True, 3.0, 1.0, 3, False) #last accept commit didn't count due to being over rejection limit
        assert entrymap["B"] == (1, False, 3.0, 2.5, 2, True)
        assert entrymap["Task1"] == (2, False, 1.0, 1.0, 0, False) #rejection not counted, because it wasn't requested
        assert entrymap["Task2"] == (3, False, 1.0, 2.0, 0, False) #accepting not counted, because it wasn't requested
        table = []
        s.report_student_work_so_far(course, entries, workhours_total, timevalue_total, table)
        assert ("A", "3.00", "1.00", r.REJECT_MARK) in table
        assert ("B", "3.00", "2.50", f"{i.ACCEPT_SYMBOL} {i.REJECT_SYMBOL}*2/3") in table
        assert ("Task1", "1.00", "1.00", "") in table
        assert ("Task2", "1.00", "2.00", "") in table

    run_inside_repo(preparations, assertions, coursemodifications)
