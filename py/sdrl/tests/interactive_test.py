import sdrl.repo as r
import sdrl.interactive as i
import sdrl.subcmd.student as s
import sdrl.subcmd.instructor as ins

from repo_test import commit, request_grading, grade, run_inside_repo

def test_interactive_requirement_grading():
    def preparations(step):
        commit("%A 1h", "%requiresA 1h", "%requiresRequiresA 1h", "%B 1h", "%requiresB 1h")
        request_grading("A", "requiresB")
        if step < 2:
            return
        grade({"A": r.ACCEPT_MARK, "requiresB": r.REJECT_MARK}) #the later should not count, as B isn't done yet
        request_grading("requiresRequiresA", "requiresA", "B") #accepting both at once should work!
        if step < 3:
            return
        grade({"requiresA": r.ACCEPT_MARK, "requiresRequiresA": r.ACCEPT_MARK, "B": r.REJECT_MARK})
        request_grading("requiresB")

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"

    def grade_input_assertions(step, entries, selected, rejected, course_url):
        if step == 1: #requiresB should not be shown at all
            assert len(entries) == 1
            assert entries[0][0] == "A"
        if step == 2: #both A successors should be there at once
            assert len(entries) == 3
            names = [e[0] for e in entries]
            assert "requiresRequiresA" in names
            assert "requiresA" in names
            assert "B" in names
        if step == 3: #requiresB is now allowed
            assert len(entries) == 1
            assert entries[0][0] == "requiresB"

    def assertions(course, step):
        entries, _, _ = r.student_work_so_far(course)
        opentasks = ins.rewrite_submission_file(course, r.SUBMISSION_FILE)
        entries = [entry for entry in entries if ins.allow_grading(course, opentasks, entry, False)]
        i.grade_entries(entries, None, False, lambda e, s, r, c: grade_input_assertions(step, e, s, r, c))

    run_inside_repo(lambda: preparations(1), lambda course: assertions(course, 1), coursemodifications)
    run_inside_repo(lambda: preparations(2), lambda course: assertions(course, 2), coursemodifications)
    run_inside_repo(lambda: preparations(3), lambda course: assertions(course, 3), coursemodifications)

def test_grading_mistakes():
    def preparations():
        commit("%A 1h", "%B 1h", "%requiresA 1h", "%requiresB 1h")
        request_grading("A", "B")
        grade({"A": r.REJECT_MARK, "B": r.ACCEPT_MARK}) #initial false gradings
        request_grading("requiresA", "requiresB")

    def coursemodifications(course_json):
        course_json["allowed_attempts"] = "1"
        
    def grade_input_assertions(override, entries, selected, rejected, course_url):
        assert len(entries) == 2
        names = [e[0] for e in entries]
        assert ("A" if override else "requiresA") in names
        assert ("B" if override else "requiresB") in names
        if override: #actively override!
            assert selected["B"]
            assert rejected["A"]
            selected["B"] = False
            rejected["B"] = True
        else:
            assert all(v == False for v in selected.values())
            assert all(v == False for v in rejected.values())
            selected["requiresA"] = True
            rejected["requiresB"] = True

    def assertions(course):
        entries, _, _= r.student_work_so_far(course)
        opentasks = ins.rewrite_submission_file(course, r.SUBMISSION_FILE)
        for override in [False, True]:
            allowed = [entry for entry in entries if ins.allow_grading(course, opentasks, entry, override)]
            assert len(allowed) == 2
            rejections = i.grade_entries(allowed, None, override, lambda e, s, r, c: grade_input_assertions(override, e, s, r, c))
            output = r.submission_file_entries(allowed, rejections, override)
            if override:
                assert len(rejections) == 1
                assert "B" in rejections #actually overridden
                assert len(allowed) == 1 #A didn't change, so no override should happen!
                assert allowed[0][0] == "B"
                assert len(output) == 1
                assert output["B"] == r.OVERRIDE_PREFIX + r.REJECT_MARK
            else:
                assert len(rejections) == 1
                assert "requiresB" in rejections
                assert all(entry[4] == (entry[0] == "requiresA") for entry in allowed)
                assert len(output) == 2
                assert output["requiresA"] == r.ACCEPT_MARK
                assert output["requiresB"] == r.REJECT_MARK

    run_inside_repo(preparations, assertions, coursemodifications)
