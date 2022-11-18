# pytest tests. Some of them work on Linux only (just like sedrila overall).

import json
import os
import re
import subprocess
import tempfile

import pytest

import base as b
import git
import sdrl.course
import sdrl.student

GIT_USER = "user@example.org"

class HomeHereContextMgr:
    def __init__(self, dir):
        self.newdir = dir

    def __enter__(self):
        self.origdir = os.getcwd()
        os.chdir(self.newdir)
        self.home = os.environ['HOME']
        os.environ['HOME'] = "."
        return self.origdir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.environ['HOME'] = self.home
        os.chdir(self.origdir)


def create_git_repo():
    os.system(f"git config --global user.email {GIT_USER}")
    os.system("git config --global user.name 'Dummy Instructor'")
    os.system("git init -b main")
    os.system("git commit --allow-empty -m'hello'")
    os.system("git commit --allow-empty -m'A 3.25h'")
    os.system("git commit --allow-empty -m'A 0:45h'")
    b.spit("submission.yaml", f"submission:\n A: {sdrl.student.REJECT_MARK}  some comment about the problem\n")
    os.system("git add submission.yaml")
    os.system("git commit -S -m'submission.yaml checked'")
    os.system("gpgconf --kill gpg-agent")


def create_gpg_key() -> str:
    os.system("gpgconf --kill gpg-agent")
    os.system(f"gpg --quick-gen-key --batch --pinentry-mode loopback --passphrase '' {GIT_USER} default default never")
    fpr_output = subprocess.check_output("HOME=. gpg --fingerprint --with-colons", shell=True)
    print("create_gpg_key:", fpr_output)
    mm = re.search(rb"fpr:+([0-9A-F]+)", fpr_output)
    assert mm
    return str(mm.group(1))  # the fingerprint-proper only


@pytest.mark.skip("commit signing does not work")
def test_student_work_so_far():
    with tempfile.TemporaryDirectory() as tempdir, HomeHereContextMgr(tempdir) as origdir:
        #----- initialize test environment:
        with open(f"{origdir}/py/sdrl/tests/data/{sdrl.course.METADATA_FILE}", 'r', encoding='utf8') as f:
            course_json = json.load(f)  # course config template
        fingerprint = create_gpg_key()
        course_json['instructors'][0]['fingerprint'] = fingerprint  
        with open(sdrl.course.METADATA_FILE, 'wt', encoding='utf8') as f:
            json.dump(course_json, f)  # final course config
        create_git_repo()
        #----- initialize application environment:
        course = sdrl.course.Course(sdrl.course.METADATA_FILE, read_contentfiles=False)
        commits = git.get_commits()
        workhours = sdrl.student.get_workhours(commits)
        sdrl.student.accumulate_workhours_per_task(workhours, course)
        hashes = sdrl.student.get_submission_checked_commits(course, commits)
        print("hashes:", hashes)
        checked_tuples = sdrl.student.get_all_checked_tuples(hashes)
        print("checked_tuples:", checked_tuples)
        sdrl.student.accumulate_timevalues_and_attempts(checked_tuples, course)
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = sdrl.student.student_work_so_far(course)
        print("ReportEntries: ", entries)
        assert workhours_total == 4.0
        assert timevalue_total == 0.0
        assert len(entries) == 1
        assert entries[0] == ("A", 4.0, 1.0, "R")


def test_parse_taskname_workhours():
    func = sdrl.student.parse_taskname_workhours
    assert func("mystuff 1h remaining msg") == ("mystuff", 1.0)
    assert func("mystuff 1h") == ("mystuff", 1.0)
    assert func("mystuff 1 h") == ("mystuff", 1.0)
    assert func("mystuff 1.0h") == ("mystuff", 1.0)
    assert func("mystuff 1:00h") == ("mystuff", 1.0)
    assert func("my-stuff 1h") is None
    assert func("SomeTask4711 0:01h 1001 nights message") == ("SomeTask4711", 1.0/60)
    assert func("a 11.5h   ") == ("a", 11.50)
    assert func("a 1111:45h") == ("a", 1111.750)
