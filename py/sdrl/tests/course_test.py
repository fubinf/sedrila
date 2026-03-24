"""Unit tests for sdrl/course.py — properties and methods testable without full course build."""
import datetime as dt
import logging
import types
import unittest.mock as mock

import pytest

import base as b
import sdrl.constants as c
import sdrl.course as course
from sdrl.course import Course, Task


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

def make_mock_task(name="task1", assumes=None, accept_date=None, rejections=0,
                   timevalue=2.0, remaining_attempts=2):
    """Minimal mock for Task property tests — bypasses the real constructor."""
    t = mock.MagicMock()
    t.name = name
    t.assumes = assumes or []
    t.accept_date = accept_date
    t.rejections = rejections
    t.timevalue = timevalue
    t.is_accepted = accept_date is not None
    t.remaining_attempts = remaining_attempts
    return t


def make_mock_course(tasks: dict = None):
    """Course-like object with a namespace and task() method."""
    ns = tasks or {}
    obj = types.SimpleNamespace(
        namespace=dict(ns),
        _tasks=dict(ns),
    )
    obj.task = lambda name: obj._tasks.get(name)
    return obj


# ── Task.is_accepted ──────────────────────────────────────────────────────────

def test_task_is_accepted_when_accept_date_set():
    t = types.SimpleNamespace(accept_date=dt.datetime(2024, 1, 1))
    assert Task.is_accepted.fget(t) is True


def test_task_is_not_accepted_when_accept_date_none():
    t = types.SimpleNamespace(accept_date=None)
    assert Task.is_accepted.fget(t) is False


# ── Task.acceptance_state ─────────────────────────────────────────────────────

def test_acceptance_state_accepted():
    t = make_mock_task(accept_date=dt.datetime(2024, 1, 1))
    assert Task.acceptance_state.fget(t) == c.SUBMISSION_ACCEPT_MARK


def test_acceptance_state_rejected_no_attempts_left():
    t = make_mock_task(rejections=3, remaining_attempts=0)
    assert Task.acceptance_state.fget(t) == c.SUBMISSION_REJECT_MARK


def test_acceptance_state_rejectoid_has_attempts():
    t = make_mock_task(rejections=1, remaining_attempts=1)
    assert Task.acceptance_state.fget(t) == c.SUBMISSION_REJECTOID_MARK


def test_acceptance_state_none():
    t = make_mock_task(rejections=0, remaining_attempts=2)
    assert Task.acceptance_state.fget(t) == c.SUBMISSION_NONCHECK_MARK


# ── Task.time_earned ──────────────────────────────────────────────────────────

def test_time_earned_accepted():
    t = types.SimpleNamespace(is_accepted=True, timevalue=3.5)
    assert Task.time_earned.fget(t) == pytest.approx(3.5)


def test_time_earned_not_accepted():
    t = types.SimpleNamespace(is_accepted=False, timevalue=3.5)
    assert Task.time_earned.fget(t) == pytest.approx(0.0)


# ── Course.has_participantslist ───────────────────────────────────────────────

def test_has_participantslist_returns_none():
    # The property body is just `False` (missing `return`), so it returns None.
    obj = types.SimpleNamespace()
    result = Course.has_participantslist.fget(obj)
    assert result is None  # documents the existing (buggy) behaviour


# ── Course.get_part ───────────────────────────────────────────────────────────

def test_get_part_existing():
    part = types.SimpleNamespace(name="mytask")
    obj = types.SimpleNamespace(namespace={"mytask": part})
    result = Course.get_part(obj, "ctx", "mytask")
    assert result is part


def test_get_part_missing_returns_self_and_emits_error(capsys):
    b.loglevel = logging.ERROR
    obj = types.SimpleNamespace(namespace={})
    result = Course.get_part(obj, "ctx", "missing")
    assert result is obj
    assert b.num_errors == 1


# ── Course.namespace_add ──────────────────────────────────────────────────────

def test_namespace_add_new_part():
    obj = types.SimpleNamespace(namespace={})
    part = types.SimpleNamespace(name="t1")
    Course.namespace_add(obj, part)
    assert obj.namespace["t1"] is part


def test_namespace_add_collision_raises():
    existing = types.SimpleNamespace(name="t1", sourcefile="ch1/tg1/t1.md")
    newcomer = types.SimpleNamespace(name="t1", sourcefile="ch2/tg1/t1.md")
    obj = types.SimpleNamespace(namespace={"t1": existing})
    obj._partpath = Course._partpath  # static method, attach directly
    with pytest.raises(b.CritialError):
        Course.namespace_add(obj, newcomer)


# ── Course.get_all_assumed_tasks ──────────────────────────────────────────────

def test_get_all_assumed_tasks_direct():
    t1 = types.SimpleNamespace(name="t1", assumes=["t2", "t3"])
    t2 = types.SimpleNamespace(name="t2", assumes=[])
    t3 = types.SimpleNamespace(name="t3", assumes=[])
    obj = make_mock_course({"t1": t1, "t2": t2, "t3": t3})
    result = Course.get_all_assumed_tasks(obj, "t1")
    assert result == {"t2", "t3"}


def test_get_all_assumed_tasks_transitive():
    t1 = types.SimpleNamespace(name="t1", assumes=["t2"])
    t2 = types.SimpleNamespace(name="t2", assumes=["t3"])
    t3 = types.SimpleNamespace(name="t3", assumes=[])
    obj = make_mock_course({"t1": t1, "t2": t2, "t3": t3})
    result = Course.get_all_assumed_tasks(obj, "t1")
    assert result == {"t2", "t3"}


def test_get_all_assumed_tasks_excludes_self():
    t1 = types.SimpleNamespace(name="t1", assumes=["t2"])
    t2 = types.SimpleNamespace(name="t2", assumes=[])
    obj = make_mock_course({"t1": t1, "t2": t2})
    result = Course.get_all_assumed_tasks(obj, "t1")
    assert "t1" not in result


def test_get_all_assumed_tasks_cycle_safe():
    t1 = types.SimpleNamespace(name="t1", assumes=["t2"])
    t2 = types.SimpleNamespace(name="t2", assumes=["t1"])  # cycle
    obj = make_mock_course({"t1": t1, "t2": t2})
    result = Course.get_all_assumed_tasks(obj, "t1")  # must not loop
    assert result == {"t2"}


def test_get_all_assumed_tasks_missing_assumed_task():
    t1 = types.SimpleNamespace(name="t1", assumes=["nonexistent"])
    obj = make_mock_course({"t1": t1})
    result = Course.get_all_assumed_tasks(obj, "t1")  # nonexistent task ignored
    assert result == set()


# ── Course._parse_allowed_attempts ────────────────────────────────────────────

def test_parse_allowed_attempts_full_format():
    obj = types.SimpleNamespace(allowed_attempts="2 + 0.5/h",
                                sourcefile="sedrila.yaml")
    base, hourly = Course._parse_allowed_attempts(obj)
    assert base == 2
    assert hourly == pytest.approx(0.5)


def test_parse_allowed_attempts_base_only():
    obj = types.SimpleNamespace(allowed_attempts="3", sourcefile="sedrila.yaml")
    base, hourly = Course._parse_allowed_attempts(obj)
    assert base == 3
    assert hourly == pytest.approx(0.0)


def test_parse_allowed_attempts_invalid_format():
    b.loglevel = logging.ERROR
    obj = types.SimpleNamespace(allowed_attempts="invalid", sourcefile="sedrila.yaml")
    base, hourly = Course._parse_allowed_attempts(obj)
    assert base == 2     # fallback
    assert hourly == 0   # fallback
    assert b.num_errors == 1


# ── Course._partpath ──────────────────────────────────────────────────────────

def test_partpath_index_md_returns_dirname():
    part = types.SimpleNamespace(sourcefile="/some/path/ch1/index.md")
    result = Course._partpath(part)
    assert result == "/some/path/ch1"


def test_partpath_regular_file_returns_fullpath():
    part = types.SimpleNamespace(sourcefile="/some/path/task1.md")
    result = Course._partpath(part)
    assert result == "/some/path/task1.md"
