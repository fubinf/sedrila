"""Unit tests for sdrl/directory.py."""
import logging
import unittest.mock as mock

import base as b
from sdrl.directory import Directory


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

class _FakeElem:
    """Minimal stand-in element — accepts any kwargs, has a build() method."""
    def __init__(self, name, **kwargs):
        self.name = name
    def build(self):
        pass


class _FakeElem2:
    """Second fake type for multi-type tests."""
    def __init__(self, name, **kwargs):
        self.name = name
    def build(self):
        pass


def _make_directory() -> Directory:
    """Return a Directory with a real cache mock plus two fake element types registered."""
    cache = mock.MagicMock()
    d = Directory(cache)
    # Attach fake types so they can be used without importing real element classes
    d.managed_types.append(_FakeElem)
    d.managed_types.append(_FakeElem2)
    d.fakeeelem = {}   # intentional typo avoidance: use the classname lowercased
    setattr(d, _FakeElem.__name__.lower(), {})
    setattr(d, _FakeElem2.__name__.lower(), {})
    return d


# ── get_the ───────────────────────────────────────────────────────────────────

def test_get_the_missing_returns_none():
    d = _make_directory()
    assert d.get_the(_FakeElem, "nonexistent") is None


def test_get_the_existing_returns_instance():
    d = _make_directory()
    obj = _FakeElem("myname")
    getattr(d, _FakeElem.__name__.lower())["myname"] = obj
    assert d.get_the(_FakeElem, "myname") is obj


# ── make_the ─────────────────────────────────────────────────────────────────

def test_make_the_creates_and_stores():
    d = _make_directory()
    result = d.make_the(_FakeElem, "e1")
    assert isinstance(result, _FakeElem)
    assert d.get_the(_FakeElem, "e1") is result


def test_make_the_overwrite_logs_debug():
    d = _make_directory()
    d.make_the(_FakeElem, "e1")
    b.loglevel = logging.DEBUG
    with mock.patch("base.rich_print") as mock_print:
        d.make_the(_FakeElem, "e1")   # second call → overwrite path (line 45)
        args = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        assert "make_the" in args or "overwriting" in args or mock_print.called


# ── take_the ─────────────────────────────────────────────────────────────────

def test_take_the_stores_existing_instance():
    d = _make_directory()
    obj = _FakeElem("e2")
    d.take_the(_FakeElem, "e2", obj)
    assert d.get_the(_FakeElem, "e2") is obj


def test_take_the_overwrite_logs_debug():
    d = _make_directory()
    obj1 = _FakeElem("e3")
    obj2 = _FakeElem("e3")
    d.take_the(_FakeElem, "e3", obj1)
    b.loglevel = logging.DEBUG
    with mock.patch("base.rich_print") as mock_print:
        d.take_the(_FakeElem, "e3", obj2)   # overwrite path (line 53-54)
        assert mock_print.called


# ── make_or_get_the ───────────────────────────────────────────────────────────

def test_make_or_get_the_returns_existing():
    d = _make_directory()
    obj = d.make_the(_FakeElem, "e4")
    result = d.make_or_get_the(_FakeElem, "e4")
    assert result is obj


def test_make_or_get_the_creates_if_missing():
    d = _make_directory()
    result = d.make_or_get_the(_FakeElem, "e5")
    assert isinstance(result, _FakeElem)


# ── record_the ────────────────────────────────────────────────────────────────

def test_record_the_stores_instance():
    d = _make_directory()
    obj = _FakeElem("e6")
    d.record_the(_FakeElem, "e6", obj)
    assert d.get_the(_FakeElem, "e6") is obj


def test_record_the_same_instance_no_debug():
    d = _make_directory()
    obj = _FakeElem("e7")
    d.record_the(_FakeElem, "e7", obj)
    b.loglevel = logging.DEBUG
    with mock.patch("base.rich_print") as mock_print:
        d.record_the(_FakeElem, "e7", obj)   # same instance → no debug
        assert not mock_print.called


def test_record_the_different_instance_logs_debug():
    d = _make_directory()
    obj1 = _FakeElem("e8")
    obj2 = _FakeElem("e8")
    d.record_the(_FakeElem, "e8", obj1)
    b.loglevel = logging.DEBUG
    with mock.patch("base.rich_print") as mock_print:
        d.record_the(_FakeElem, "e8", obj2)  # different instance → debug (line 65)
        assert mock_print.called


# ── get_all ───────────────────────────────────────────────────────────────────

def test_get_all_by_type_returns_all_of_that_type():
    d = _make_directory()
    a = d.make_the(_FakeElem, "a")
    b_ = d.make_the(_FakeElem, "b")
    result = list(d.get_all(_FakeElem))
    assert a in result
    assert b_ in result


def test_get_all_by_name_returns_across_types():
    d = _make_directory()
    e1 = _FakeElem("shared")
    e2 = _FakeElem2("shared")
    d.take_the(_FakeElem, "shared", e1)
    d.take_the(_FakeElem2, "shared", e2)
    result = list(d.get_all("shared"))   # string → name lookup (lines 80-85)
    assert e1 in result
    assert e2 in result


def test_get_all_by_name_not_found_returns_empty():
    d = _make_directory()
    result = list(d.get_all("does_not_exist"))
    assert result == []


# ── build ─────────────────────────────────────────────────────────────────────

def test_build_calls_build_on_all_elements():
    d = _make_directory()
    e1 = mock.MagicMock()
    e2 = mock.MagicMock()
    d.take_the(_FakeElem, "e1", e1)
    d.take_the(_FakeElem2, "e2", e2)
    d.build()
    e1.build.assert_called_once()
    e2.build.assert_called_once()
