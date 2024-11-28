import typing as tg

import sdrl.constants as c
import sdrl.interactive as i
import sdrl.repo as r
import sdrl.subcmd.instructor as ins

import repo_test as rt


def test_interactive_requirement_grading():
    def preparations(step: int):
        rt.commit("%A 1h", "%requiresA 1h", "%requiresRequiresA 1h", "%B 1h", "%requiresB 1h")
        rt.request_grading("A", "requiresB")
        if step < 2:
            return
        rt.grade({"A": c.SUBMISSION_ACCEPT_MARK, 
                  "requiresB": c.SUBMISSION_REJECT_MARK})  # note that B isn't done yet
        rt.request_grading("requiresRequiresA", "requiresA", "B")  # accepting both at once should work!
        if step < 3:
            return
        rt.grade({"requiresA": c.SUBMISSION_ACCEPT_MARK, "requiresRequiresA": c.SUBMISSION_ACCEPT_MARK, 
                  "B": c.SUBMISSION_REJECT_MARK})
        rt.request_grading("requiresB")

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def grade_input_assertions(step: int, entries: tg.Sequence[r.ReportEntry], selected, rejected, course_url):
        if step == 1:  # requiresB should not be shown at all
            assert len(entries) == 1
            assert entries[0].taskname == "A"
        if step == 2:  # both A successors should be there at once
            assert len(entries) == 3
            names = [e.taskname for e in entries]
            assert "requiresRequiresA" in names
            assert "requiresA" in names
            assert "B" in names
        if step == 3:  # requiresB was rejected before (when B had not been accepted)
            assert len(entries) == 0

    def assertions(course, step: int):
        entries, _, _ = r.student_work_so_far(course)
        opentasks = ins.rewrite_submission_file(course, c.SUBMISSION_FILE)
        entries = [entry for entry in entries if ins.allow_grading(course, opentasks, entry, False)]
        i.grade_entries(entries, "", False, lambda e, s, r, c: grade_input_assertions(step, e, s, r, c))

    rt.run_inside_repo(lambda: preparations(1), lambda course: assertions(course, 1), coursemodifications)
    rt.run_inside_repo(lambda: preparations(2), lambda course: assertions(course, 2), coursemodifications)
    rt.run_inside_repo(lambda: preparations(3), lambda course: assertions(course, 3), coursemodifications)


def test_grading_mistakes():
    def preparations():
        rt.commit("%A 1h", "%B 1h", "%requiresA 1h", "%requiresB 1h")
        rt.request_grading("A", "B")
        rt.grade({"A": c.SUBMISSION_REJECT_MARK, "B": c.SUBMISSION_ACCEPT_MARK})  # mistaken gradings
        rt.request_grading("requiresA", "requiresB")  # both allowed, even though A was rejected

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"
        
    def grade_input_assertions(override: bool, entries: tg.Sequence[r.ReportEntry], selected, rejected, course_url):
        assert len(entries) == 2
        names = {e.taskname for e in entries}
        if not override:  # first call
            assert names == {"requiresA", "requiresB"}
            assert all(not v for v in selected.values())
            assert all(not v for v in rejected.values())
            selected["requiresA"] = True
            rejected["requiresB"] = True
        if override:  # second call
            assert names == {"A", "B"}  # with override, offer only previous gradings
            print("### selected/rejected:", selected, rejected)
            assert selected["B"]
            assert rejected["A"]
            selected["B"] = False
            rejected["B"] = True

    def assertions(course):
        entries, _, _ = r.student_work_so_far(course)
        opentasks = ins.rewrite_submission_file(course, c.SUBMISSION_FILE)
        for override in [False, True]:
            allowed = [entry for entry in entries if ins.allow_grading(course, opentasks, entry, override)]
            assert len(allowed) == 2
            rejections = i.grade_entries(allowed, "", override, 
                                         lambda e, s, r, c: grade_input_assertions(override, e, s, r, c))
            output = r.submission_file_entries(allowed, rejections, override)
            if override:
                assert len(rejections) == 1
                assert "B" in rejections  # actually overridden
                assert len(allowed) == 1  # A didn't change, so no override should happen!
                assert allowed[0][0] == "B"
                assert len(output) == 1
                assert output["B"] == c.SUBMISSION_OVERRIDE_PREFIX + c.SUBMISSION_REJECT_MARK
            else:
                assert len(rejections) == 1
                assert "requiresB" in rejections
                assert all(entry.accepted == (entry.taskname == "requiresA") for entry in allowed)
                assert len(output) == 2
                assert output["requiresA"] == c.SUBMISSION_ACCEPT_MARK
                assert output["requiresB"] == c.SUBMISSION_REJECT_MARK

    rt.run_inside_repo(preparations, assertions, coursemodifications)
