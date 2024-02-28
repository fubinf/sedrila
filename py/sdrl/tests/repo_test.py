# pytest tests. Some of them work on Linux only (just like sedrila overall).

from itertools import chain
import os
import re
import subprocess

import pytest

import base as b
import git
import sdrl.course
import sdrl.repo as r
import sdrl.subcmd.student

from tests.testbase import TempDirEnvironContextMgr

GIT_USER = "user@example.org"
INSTRUCTOR_USER = "instructor"

def init_repo():
    os.system("git config user.name 'SeDriLa Dummy'")
    os.system("git init -b main")

def commit(*args, **kwargs):
    signed = kwargs.pop('signed', False)
    user = kwargs.pop('user', "user")
    if signed:
        os.system("gpgconf --kill gpg-agent")
    os.system(f"git config user.email {user}@example.org")
    for message in args:
        gitcmd = f"git commit {'-S' if signed else ''} --allow-empty -m'{message}'"
        if signed:
            gitcmd = f"GPG_TTY=$(tty) gpg-agent --daemon -- {gitcmd}"
        os.system(gitcmd)
    if signed:
        os.system("gpgconf --kill gpg-agent")

def grade(grades):
    b.spit_yaml(r.SUBMISSION_FILE, grades)
    os.system(f"git add '{r.SUBMISSION_FILE}'")
    commit(f"{r.SUBMISSION_FILE} checked", user=INSTRUCTOR_USER, signed=True)

def create_gpg_key() -> str:
    os.system("gpgconf --kill gpg-agent")
    os.system(f"gpg --quick-gen-key --batch --pinentry-mode loopback --passphrase '' {GIT_USER} default default never")
    fpr_output = subprocess.check_output("HOME=. gpg --fingerprint --with-colons", shell=True)
    print("create_gpg_key:", fpr_output)
    mm = re.search(rb"fpr:+([\dA-F]+)", fpr_output)
    assert mm
    return str(mm.group(1))  # the fingerprint-proper only

def test_student_work_so_far():
    def preparations():
        commit("hello", "%A 3.25h", "%A 0:45h"),
        grade({"A", f"{r.REJECT_MARK}  some comment about the problem\n"})

    def assertions(course, commits):
        hasheslists = r.submission_checked_commit_hashes(course, commits)
        hashes = list(chain.from_iterable(hasheslists))
        print("hashes:", hashes)
        checked_tuples = r.checked_tuples_from_commits(hashes)
        print("checked_tuples:", checked_tuples)
        r.accumulate_timevalues_and_attempts(checked_tuples, course)
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        assert workhours_total == 4.0
        assert timevalue_total == 0.0
        assert len(entries) == 1
        #assert entries[0] == ("A", 4.0, 1.0, 1, False) #why is this wrong?
        assert entries[0] == ("A", 4.0, 1.0, 0, False)

    run_inside_repo(preparations, assertions)

def run_inside_repo(preparations, assertions):
    with TempDirEnvironContextMgr(HOME='.') as mgr:
        #----- initialize test environment:
        course_json = b.slurp_json(f"{mgr.origdir}/py/sdrl/tests/data/{b.METADATA_FILE}")  # config template
        fingerprint = create_gpg_key()
        course_json['instructors'][0]['fingerprint'] = fingerprint  
        b.spit_json(b.METADATA_FILE, course_json)  # final course config
        init_repo()
        preparations()
        #----- initialize application environment:
        course = sdrl.course.Course(b.METADATA_FILE, read_contentfiles=False, include_stage="")
        commits = git.commits_of_local_repo()
        workhours = r.workhours_of_commits(commits)
        r.accumulate_workhours_per_task(workhours, course)
        assertions(course, commits)


def test_parse_taskname_workhours():
    func = r._parse_taskname_workhours
    assert func("%mystuff 1h remaining msg") == ("mystuff", 1.0)
    assert func("%mystuff 1h") == ("mystuff", 1.0)
    assert func(" %mystuff 1h") == ("mystuff", 1.0)
    assert func("%mystuff 1 h") == ("mystuff", 1.0)
    assert func("%mystuff 1.0h") == ("mystuff", 1.0)
    assert func("%mystuff 1:00h") == ("mystuff", 1.0)
    assert func("%my-stuff 1h") is None
    assert func("%SomeTask4711 0:01h 1001 nights message") == ("SomeTask4711", 1.0/60)
    assert func("%a 11.5h   ") == ("a", 11.50)
    assert func("%a 1111:45h") == ("a", 1111.750)
