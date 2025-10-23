import argparse
import contextlib
import os
import shutil
import unittest.mock

import base as b
import sgit
import sdrl.constants as c
import sdrl.course
import sdrl.participant

import tests.testbase as tb

TEST_REPO = "git@github.com:fubinf/sedrila-test1.git"
METADATA_FILE = f"{os.path.dirname(__file__)}/data/{c.METADATA_FILE}"

student_yaml = """
course_url: file://../coursedir
student_name: Me Student
student_id: 12345
student_gituser: mestudent
partner_gituser: ""
"""


def test_participant(capfd):
    """
    Tests sdrl.repo, sdrl.participant.
    Deep-integrationey test: Accesses external server, creates+deletes directories etc.
    """
    with tb.TempDirEnvironContextMgr() as mgr:
        empty = argparse.Namespace()
        
        # ----- test clone:
        b._testmode_reset()
        os.mkdir("instructordir")
        os.chdir("instructordir")
        sgit.clone(TEST_REPO, "studentdir")
        git_stderr = capfd.readouterr().err
        assert "Cloning into" in git_stderr
        assert not "Permission denied" in git_stderr, "clone failed, do you have an ssh key?"
        with open("studentdir/student.yaml", 'wt') as f:
            f.write(student_yaml)
        
        # ----- make pseudo-coursedir:
        os.mkdir('coursedir')
        shutil.copy(METADATA_FILE, 'coursedir')
        # with contextlib.chdir("studentdir"):
        #     os.system("git log|cat")
        
        # ----- test Context:
        ctx = sdrl.participant.make_context(empty, ["studentdir"], is_instructor=False, show_size=True)
        student = ctx.studentlist[0]  # there is only one
        assert ctx.submission_tasknames == {'Task1'}
        assert student.submission_tasknames == {'Task1'}
        assert "/task/Task1.md" in ctx.submission_pathset
        assert "/task/Task1.md" in student.submission_pathset
        assert "/task/Task3.md" not in ctx.submission_pathset
        assert "/task/Task3.md" not in student.submission_pathset
        assert "/task/Task3.md" in ctx.pathset
        assert "/task/Task3.md" in student.pathset
        task1, task2 = student.course_with_work.task('Task1'), student.course_with_work.task('Task2')
        assert (task1.timevalue, task2.timevalue) == (1.0, 2.0)
        assert (task1.workhours, task2.workhours) == (1.0, 0.5)
        assert not task1.is_accepted 
        
        # ----- perform accepting/rejecting:
        submission = dict(Task1=c.SUBMISSION_CHECK_MARK, Task2=c.SUBMISSION_CHECK_MARK)
        filename = os.path.join(student.topdir, c.SUBMISSION_FILE)
        b.spit_yaml(filename, submission)
        ctx = sdrl.participant.make_context(empty, ["studentdir"], is_instructor=True)
        student = ctx.studentlist[0]  # now with the above submission file
        print("#1:", student.submission)
        student.set_state("Task1", sdrl.participant.SubmissionTaskState.ACCEPT)
        print("#2:", student.submission)
        assert student.submissions.task("Task1").state == sdrl.participant.SubmissionTaskState.ACCEPT
        assert student.submission["Task1"] == c.SUBMISSION_ACCEPT_MARK 

        student.set_state("Task2", sdrl.participant.SubmissionTaskState.REJECT)
        print("#3:", student.submission)
        assert student.submissions.task("Task2").state == sdrl.participant.SubmissionTaskState.REJECT
        assert student.submission["Task2"] == c.SUBMISSION_REJECT_MARK 

        with contextlib.chdir(student.topdir):  # make unsigned commit, we will mock the signature check
            sgit.make_commit(*[c.SUBMISSION_FILE], msg=c.SUBMISSION_CHECKED_COMMIT_MSG, signed=False)
        
        # ----- check result of accepting/rejecting:
        def all_signers_allowed(commit, allowed_signers):
            print("all_signers_allowed:", commit)
            return True
        with unittest.mock.patch('sdrl.repo.is_allowed_signer', new=all_signers_allowed):  # believe everything
            ctx = sdrl.participant.make_context(empty, ["studentdir"], is_instructor=True)
        student = ctx.studentlist[0]  # there is only one
        print("#4:", student.submission)
        task1, task2 = student.course_with_work.task('Task1'), student.course_with_work.task('Task2')
        assert (task1.workhours, task2.workhours) == (1.0, 0.5)
        assert task1.is_accepted 
        assert not task2.is_accepted
        assert (task1.rejections, task2.rejections) == (0, 1)
