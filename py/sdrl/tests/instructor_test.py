import json
import os
import shutil
import unittest.mock

import base as b
import git
import sdrl.course
import sdrl.repo as r
import sdrl.subcmd.instructor as sut  # system under test
import tests.testbase as tb

TEST_REPO = "git@github.com:fubinf/sedrila-test1.git"
METADATA_FILE = f"{os.path.dirname(__file__)}/data/{b.METADATA_FILE}"


def test_instructor_parts(capfd):
    """
    Deep-integrationey test. Accesses external server, creates+deletes directories etc.
    sut.execute() is not well-suited for testing, so we test its constituent parts here.
    Not pretty due to the redundancy, but does the job OK.
    """
    with tb.TempDirEnvironContextMgr(**{sut.USER_CMD_VAR: "echo SEDRILA_INSTRUCTOR_COMMAND was called"}) as mgr:
        os.environ[sut.REPOS_HOME_VAR] = mgr.newdir  # will not be unpatched; not a problem
        # ----- test clone:
        b._testmode_reset()
        sut.checkout_student_repo(TEST_REPO, home=mgr.newdir)  # will clone
        assert "Cloning into" in capfd.readouterr().err
        assert os.getcwd().endswith(git.username_from_repo_url(TEST_REPO))
        os.chdir(mgr.newdir)
        # ----- test pull:
        b._testmode_reset()
        sut.checkout_student_repo(TEST_REPO, home=mgr.newdir)  # will pull and get "Already up to date."
        assert "Already up to date" in capfd.readouterr().out
        assert os.getcwd().endswith(git.username_from_repo_url(TEST_REPO))
        # ----- make pseudo-coursedir:
        os.mkdir('out')
        shutil.copy(METADATA_FILE, 'out')
        # ----- read data from repo:
        b._testmode_reset()
        configfile = f"out/{b.METADATA_FILE}"
        course = sdrl.course.CourseSI(configdict=b.slurp_json(configfile), context=configfile)
        r.compute_student_work_so_far(course)
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        assert entries[0] == ('Task1', 1.0, 1.0, 0, False)
        # ----- rewrite submission file:
        # the repo's submission file contains dict(Task1="CHECK", NonExistingTask3="CHECK")
        b._testmode_reset()
        sut.rewrite_submission_file(course, r.SUBMISSION_FILE)
        submission = b.slurp_yaml(r.SUBMISSION_FILE)
        assert submission['NonExistingTask3'] == r.NONTASK_MARK
        # ----- simulate invalid user editing attempt:
        with unittest.mock.patch('time.sleep'):
            sut.call_instructor_cmd(course, sut.instructor_cmd(), iteration=0)
        output = capfd.readouterr().out
        print(output)
        if False:  # due to the kludge with USER_CMD_VAR above , this part is broken 
            assert f"{sut.USER_CMD_VAR} was called" in output  # check some of the explanation
            assert os.environ[sut.USER_CMD_VAR] in output  # make sure the actual command is shown
        is_valid = sut.validate_submission_file(course, r.SUBMISSION_FILE)
        assert not is_valid
        output = capfd.readouterr().out
        assert "has neither" in output
        assert "Impossible mark" in output
        # ----- simulate valid user editing attempt:
        del submission['NonExistingTask3']  # delete nonsense entry as the instructor must
        submission['Task1'] = r.ACCEPT_MARK  # accept the other entry
        b.spit_yaml(r.SUBMISSION_FILE, submission)
        with unittest.mock.patch('time.sleep'):
            sut.call_instructor_cmd(course, sut.instructor_cmd(), iteration=1)
        output = capfd.readouterr().out
        if False:  # due to the kludge with USER_CMD_VAR above , this part is broken 
            assert f"Calling '{os.environ[sut.USER_CMD_VAR]}' again" in output  # the repeat blurb
        assert sut.validate_submission_file(course, r.SUBMISSION_FILE)
        # ----- finish:
        def pseudo_push():
            assert last_commit.hash != git.commits_of_local_repo()[0].hash
            git.discard_commits(1)  # undo the r.SUBMISSION_FILE commit
        last_commit = git.commits_of_local_repo()[0]  # remember it to check the test itself
        with unittest.mock.patch('git.push', new=pseudo_push):
            sut.commit_and_push(r.SUBMISSION_FILE)
        output = capfd.readouterr().out
        assert "submission.yaml checked" in output
        last_commit2 = git.commits_of_local_repo()[0]
        assert last_commit.hash == last_commit2.hash  # has pseudo_push done the discard correctly?
