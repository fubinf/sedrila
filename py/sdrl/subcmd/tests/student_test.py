"""Unit tests for sdrl/subcmd/student.py."""
import argparse
import logging
import types
import unittest.mock as mock

import pytest

import base as b
import sdrl.constants as c
import sdrl.subcmd.student as student


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

def make_task(name="t1", workhours=1.0, is_accepted=False,
              remaining_attempts=2, rejections=0):
    return types.SimpleNamespace(
        name=name,
        workhours=workhours,
        is_accepted=is_accepted,
        remaining_attempts=remaining_attempts,
        rejections=rejections,
    )


def make_student(submission: dict, taskdict: dict = None):
    """Minimal student-like object for cmd_prepare tests."""
    taskdict = taskdict or {}

    def task_lookup(name):
        return taskdict.get(name)

    course = types.SimpleNamespace(
        task=task_lookup,
        taskdict=taskdict,
    )
    s = types.SimpleNamespace(
        submissionfile_path="student.yaml",
        submission=dict(submission),   # mutable copy
        course=course,
        save_submission=mock.MagicMock(),
    )
    return s


def make_ctx(students: list):
    return types.SimpleNamespace(studentlist=students)


def make_course(instructors: list):
    return types.SimpleNamespace(instructors=instructors)


# ── cmd_prepare ───────────────────────────────────────────────────────────────

def test_cmd_prepare_keeps_valid_check_entry():
    t1 = make_task("t1", workhours=1.0, is_accepted=False, remaining_attempts=2)
    s = make_student({"t1": c.SUBMISSION_CHECK_MARK}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert "t1" in s.submission
    assert s.submission["t1"] == c.SUBMISSION_CHECK_MARK


def test_cmd_prepare_removes_unknown_task():
    s = make_student({"ghost": c.SUBMISSION_CHECK_MARK}, taskdict={})
    student.cmd_prepare(make_ctx([s]))
    assert "ghost" not in s.submission


def test_cmd_prepare_removes_accepted_task():
    t1 = make_task("t1", is_accepted=True, remaining_attempts=2)
    s = make_student({"t1": c.SUBMISSION_CHECK_MARK}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert "t1" not in s.submission


def test_cmd_prepare_removes_task_with_no_remaining_attempts():
    t1 = make_task("t1", is_accepted=False, remaining_attempts=0)
    s = make_student({"t1": c.SUBMISSION_CHECK_MARK}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert "t1" not in s.submission


def test_cmd_prepare_removes_noncheck_entry_silently():
    t1 = make_task("t1", workhours=1.0, is_accepted=False, remaining_attempts=2)
    s = make_student({"t1": c.SUBMISSION_NONCHECK_MARK}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    # NONCHECK is removed from original submission dict but may be re-added as NONCHECK
    # since the task is eligible — confirm it ends up as NONCHECK (added fresh)
    assert s.submission.get("t1") == c.SUBMISSION_NONCHECK_MARK


def test_cmd_prepare_adds_eligible_task_as_noncheck():
    t1 = make_task("t1", workhours=2.0, is_accepted=False, remaining_attempts=3)
    s = make_student({}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert s.submission.get("t1") == c.SUBMISSION_NONCHECK_MARK


def test_cmd_prepare_does_not_add_task_without_workhours():
    t1 = make_task("t1", workhours=0.0, is_accepted=False, remaining_attempts=2)
    s = make_student({}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert "t1" not in s.submission


def test_cmd_prepare_does_not_add_accepted_task():
    t1 = make_task("t1", workhours=1.0, is_accepted=True, remaining_attempts=2)
    s = make_student({}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert "t1" not in s.submission


def test_cmd_prepare_does_not_overwrite_existing_check_entry():
    t1 = make_task("t1", workhours=1.0, is_accepted=False, remaining_attempts=2)
    s = make_student({"t1": c.SUBMISSION_CHECK_MARK}, taskdict={"t1": t1})
    student.cmd_prepare(make_ctx([s]))
    assert s.submission["t1"] == c.SUBMISSION_CHECK_MARK  # not downgraded to NONCHECK


def test_cmd_prepare_calls_save_submission():
    s = make_student({}, taskdict={})
    student.cmd_prepare(make_ctx([s]))
    s.save_submission.assert_called_once()


# ── init / import_keys validation ─────────────────────────────────────────────

def test_init_rejects_non_dot_workdir():
    with pytest.raises(b.CritialError):
        student.init(["somedir"])


def test_import_keys_rejects_non_dot_workdir():
    with pytest.raises(b.CritialError):
        student.import_keys(["somedir"])


# ── _show_instructors ─────────────────────────────────────────────────────────

def test_show_instructors_skips_without_keyfingerprint():
    course = make_course([
        {"nameish": "Alice", "email": "alice@example.com"},  # no keyfingerprint
    ])
    with mock.patch("base.rich_print") as mock_print:
        b.loglevel = logging.INFO
        student._show_instructors(course)
        # Alice has no keyfingerprint → skipped → nothing printed about her
        output = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "alice@example.com" not in output


def test_show_instructors_shows_name_and_email():
    course = make_course([
        {"nameish": "Bob", "email": "bob@example.com", "keyfingerprint": "ABCD1234"},
    ])
    with mock.patch("base.rich_print") as mock_print:
        b.loglevel = logging.INFO
        student._show_instructors(course)
        output = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "Bob" in output
        assert "bob@example.com" in output


def test_show_instructors_with_gitaccount():
    course = make_course([
        {"nameish": "Carol", "email": "carol@example.com",
         "keyfingerprint": "ABCD1234", "gitaccount": "carolg"},
    ])
    with mock.patch("base.rich_print") as mock_print:
        b.loglevel = logging.INFO
        student._show_instructors(course, with_gitaccount=True)
        output = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "carolg" in output


def test_show_instructors_without_gitaccount_hides_it():
    course = make_course([
        {"nameish": "Dave", "email": "dave@example.com",
         "keyfingerprint": "ABCD1234", "gitaccount": "daveg"},
    ])
    with mock.patch("base.rich_print") as mock_print:
        b.loglevel = logging.INFO
        student._show_instructors(course, with_gitaccount=False)
        output = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "daveg" not in output


def test_show_instructors_shows_status_lines():
    course = make_course([
        {"nameish": "Eve", "email": "eve@example.com",
         "keyfingerprint": "ABCD1234", "status": "On vacation\nBack Monday"},
    ])
    with mock.patch("base.rich_print") as mock_print:
        b.loglevel = logging.INFO
        student._show_instructors(course)
        output = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "On vacation" in output
        assert "Back Monday" in output
