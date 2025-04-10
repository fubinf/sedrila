# pytest tests. Some of them work on Linux only (just like sedrila overall).
# Creates a git repo and GPG key from scratch.

import os
import re
import subprocess

import pytest

import base as b
import sgit
import sdrl.constants as c
import sdrl.course
import sdrl.repo as r
import sdrl.subcmd.student

import tests.testbase as tb

INSTRUCTOR_USER = "sedrila-test-instructor"
GIT_USER = f"{INSTRUCTOR_USER}@example.org"


def init_repo():
    os.system("git init -b main")
    os.system("git config user.name 'SeDriLa Dummy'")


def make_commit(*args, **kwargs):
    signed = kwargs.pop('signed', False)
    user = kwargs.pop('user', "user")
    os.system(f"git config user.email {user}@example.org")
    for message in args:
        gitcmd = f"git commit {'-S' if signed else ''} --allow-empty -m'{message}'"
        print("###", gitcmd)
        os.system(with_env(gitcmd))


def request_grading(key_fingerprint, *args):
    b.spit_yaml(c.SUBMISSION_FILE, {task: c.SUBMISSION_CHECK_MARK for task in args})
    os.system(f"git add '{c.SUBMISSION_FILE}'")
    make_commit(c.SUBMISSION_COMMIT_MSG)
    assert r.submission_state('.', {key_fingerprint}) == c.SUBMISSION_STATE_FRESH


def grade(key_fingerprint, grades, signed=True):
    b.spit_yaml(c.SUBMISSION_FILE, grades)
    os.system(f"git add '{c.SUBMISSION_FILE}'")
    make_commit(c.SUBMISSION_CHECKED_COMMIT_MSG, user=INSTRUCTOR_USER, signed=signed)
    assert r.submission_state('.', {key_fingerprint}) == c.SUBMISSION_STATE_CHECKED


def with_env(command):
    return f"GPG_TTY=$(tty) HOME=. {command}"


def remove_existing_keys():
    try:
        fpr_output = subprocess.check_output(with_env(f"gpg --fingerprint --with-colons {INSTRUCTOR_USER}"), shell=True)
        fpr_lines = [line.decode("ASCII") for line in fpr_output.splitlines() if line.startswith(b"fpr:")]
        for line in fpr_lines:
            mm = re.search(r"fpr:+([\dA-F]+)", line)
            subprocess.run(with_env(f"gpg --batch --delete-secret-keys {mm.group(1)}"), shell=True)
    except Exception:
        pass


def create_gpg_key() -> str:
    os.system("gpgconf --kill gpg-agent")
    os.system(with_env("gpg-agent --daemon"))
    remove_existing_keys()
    os.system(with_env(f"gpg --quick-gen-key --batch --pinentry-mode loopback --passphrase '' "
                       f"{GIT_USER} default default never"))
    fpr_output = subprocess.check_output(with_env("gpg --fingerprint --with-colons"), shell=True)
    # print("create_gpg_key:", fpr_output)
    fpr_lines = [line.decode("ASCII") for line in fpr_output.splitlines() if line.startswith(b"fpr:")]
    mm = re.search(r"fpr:+([\dA-F]+)", fpr_lines[0])
    assert mm
    return mm.group(1)  # the fingerprint-proper only


def test_student_work_so_far():
    def preparations(key_fingerprint):
        assert r.submission_state('.', set()) == c.SUBMISSION_STATE_OTHER
        make_commit("hello", "%A 3.25h", "%A 0:45h"),
        assert r.submission_state('.', {key_fingerprint}) == c.SUBMISSION_STATE_OTHER
        request_grading(key_fingerprint, "A")
        grade(key_fingerprint, {"A": f"{c.SUBMISSION_REJECT_MARK}"})
        request_grading(key_fingerprint, "A")
        grade(key_fingerprint, {"A": f"{c.SUBMISSION_REJECT_MARK}  some comment about the problem"})

    def assertions(course):
        # subprocess.run("/bin/bash", shell=True)
        # ----- report workhours and timevalue per task:
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print("ReportEntries: ", entries)
        assert workhours_total == 4.0
        assert timevalue_total == 0.0
        assert len(entries) == 1
        assert entries[0] == r.ReportEntry("A", "basis/linuxcli/A", 4.0, 1.0, 2, False)

    run_inside_repo(preparations, assertions)


def run_inside_repo(preparations, assertions, coursemodifications=None):
    with tb.TempDirEnvironContextMgr(HOME='.') as mgr:
        # ----- initialize test environment:
        course_json = b.slurp_json(f"{mgr.origdir}/py/sdrl/tests/data/{c.METADATA_FILE}")  # config template
        fingerprint = create_gpg_key()
        course_json['instructors'][0]['keyfingerprint'] = fingerprint  
        course_json['instructors'][0]['email'] = INSTRUCTOR_USER + "@example.org"
        if coursemodifications:
            coursemodifications(course_json)
        b.spit_json(c.METADATA_FILE, course_json)  # final course config
        init_repo()
        os.system(f"git config user.signingkey {fingerprint}")
        preparations(fingerprint)
        # ----- initialize application environment:
        course = sdrl.course.CourseSI(configdict=b.slurp_json(c.METADATA_FILE), context=c.METADATA_FILE)
        commits = sgit.commits_of_local_repo(chronological=True)
        r._accumulate_student_workhours_per_task(commits, course)
        hashes = r.submission_checked_commits(course.instructors, commits)
        print("hashes:", hashes)
        checked_tuples = r.taskcheck_entries_from_commits(hashes)
        print("checked_tuples:", checked_tuples)
        r._accumulate_timevalues_and_attempts(checked_tuples, course)
        assertions(course)


def test_parse_taskname_workhours():
    func = r._parse_taskname_workhours
    assert func("%mystuff 1h remaining msg") == ("mystuff", 1.0)
    assert func("%mystuff 1h") == ("mystuff", 1.0)
    assert func(" %mystuff 1h") == ("mystuff", 1.0)
    assert func("%mystuff 1 h") == ("mystuff", 1.0)
    assert func("%mystuff 1.0h") == ("mystuff", 1.0)
    assert func("%my-stuff 1:00h") == ("my-stuff", 1.0)
    assert func("%SomeTask4711 0:01h 1001 nights message") == ("SomeTask4711", 1.0/60)
    assert func("%a 11.5h   ") == ("a", 11.50)
    assert func("%a 1111:45h") == ("a", 1111.750)
    assert func("%my stuff 1h") is None
