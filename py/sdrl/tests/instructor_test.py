import contextlib
import os
import shutil
import unittest.mock

import pytest

import base as b
import git
import sdrl.constants as c
import sdrl.course
import sdrl.participant
import sdrl.repo as r
import sdrl.subcmd.instructor as sut  # system under test

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

def test_instructor_parts(capfd):
    """
    Tests sdrl.repo, sdrl.participant, sdrl.instructor.
    Deep-integrationey test: Accesses external server, creates+deletes directories etc.
    sut.execute() is not well-suited for testing, so we test its constituent parts here.
    Not pretty due to the redundancy, but does the job OK.
    """
    # TODO 2: Move to participant_test.py. Kick out parts of repo_test.py?
    with tb.TempDirEnvironContextMgr(**{c.REPO_USER_CMD_VAR: "echo SEDRILA_INSTRUCTOR_COMMAND was called"}) as mgr:
        os.environ[c.REPOS_HOME_VAR] = mgr.newdir  # will not be unpatched; not a problem
        
        # ----- test clone:
        b._testmode_reset()
        os.mkdir("instructordir")
        os.chdir("instructordir")
        git.clone(TEST_REPO, "studentdir")
        assert "Cloning into" in capfd.readouterr().err
        with open("studentdir/student.yaml", 'wt') as f:
            f.write(student_yaml)
        
        # ----- make pseudo-coursedir:
        os.mkdir('coursedir')
        shutil.copy(METADATA_FILE, 'coursedir')
        # with contextlib.chdir("studentdir"):
        #     os.system("git log|cat")
        
        # ----- test Context:
        ctx = sdrl.participant.make_context(None, ["studentdir"], with_submission=True, show_size=True)
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
        ctx = sdrl.participant.make_context(None, ["studentdir"], with_submission=True, show_size=True)
        student = ctx.studentlist[0]  # now with the above submission file
        print("#1:", student.submission)
        while True: # horrible logic here, but natural in the webapp:
            state = student.move_to_next_state('Task1', student.submission['Task1'])
            if state == c.SUBMISSION_ACCEPT_MARK:
                break
        print("#2:", student.submission)
        assert student.submission['Task1'] == c.SUBMISSION_ACCEPT_MARK
        while True:
            state = student.move_to_next_state('Task2', student.submission['Task2'])
            if state == c.SUBMISSION_REJECT_MARK:
                break
        print("#3:", student.submission)
        assert student.submission['Task2'] == c.SUBMISSION_REJECT_MARK  # ditto in submission.yaml
        with contextlib.chdir(student.topdir):  # make unsigned commit, we will mock the signature check
            git.commit(*[c.SUBMISSION_FILE], msg=c.SUBMISSION_CHECKED_COMMIT_MSG, signed=False)
        
        # ----- check result of accepting/rejecting:
        def all_signers_allowed(commit, allowed_signers):
            print("all_signers_allowed:", commit)
            return True
        with unittest.mock.patch('sdrl.repo.is_allowed_signer', new=all_signers_allowed):  # believe everything
            ctx = sdrl.participant.make_context(None, ["studentdir"], with_submission=True, show_size=True)
        student = ctx.studentlist[0]  # there is only one
        print("#4:", student.submission)
        task1, task2 = student.course_with_work.task('Task1'), student.course_with_work.task('Task2')
        assert (task1.workhours, task2.workhours) == (1.0, 0.5)
        assert task1.is_accepted 
        assert not task2.is_accepted
        assert (task1.rejections, task2.rejections) == (0, 1)
