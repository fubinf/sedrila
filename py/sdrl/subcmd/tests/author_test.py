"""Unit tests for sdrl/subcmd/author.py."""
import argparse
import logging
import os
import types
import unittest.mock as mock

import pytest

import base as b
import sdrl.constants as c
import sdrl.subcmd.author as author


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_subparser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sp = sub.add_parser("author")
    author.add_arguments(sp)
    return sp


# ── add_arguments ─────────────────────────────────────────────────────────────

def test_add_arguments_defaults():
    args = _make_subparser().parse_args(["mydir"])
    assert args.config == c.AUTHOR_CONFIG_FILENAME
    assert args.include_stage == ''
    assert args.log == "INFO"
    assert args.sums is False
    assert args.clean is False
    assert args.rename is None
    assert args.targetdir == "mydir"


def test_add_arguments_rename_pair():
    args = _make_subparser().parse_args(["--rename", "old_part", "new_part", "mydir"])
    assert args.rename == ["old_part", "new_part"]


def test_add_arguments_clean_flag():
    args = _make_subparser().parse_args(["--clean", "mydir"])
    assert args.clean is True


def test_add_arguments_sums_flag():
    args = _make_subparser().parse_args(["--sums", "mydir"])
    assert args.sums is True


def test_add_arguments_include_stage():
    args = _make_subparser().parse_args(["--include_stage", "beta", "mydir"])
    assert args.include_stage == "beta"


# ── _targetdir_i ──────────────────────────────────────────────────────────────

def test_targetdir_i_appends_instructor_subdir():
    result = author._targetdir_i("mybuild")
    assert result == os.path.join("mybuild", c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)


def test_targetdir_i_nested_path():
    result = author._targetdir_i("/some/path/build")
    expected = os.path.join("/some/path/build", c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
    assert result == expected


# ── generate_htaccess ─────────────────────────────────────────────────────────

def test_generate_htaccess_no_template_returns_early():
    course = types.SimpleNamespace(htaccess_template=None)
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        m.assert_not_called()


def test_generate_htaccess_empty_template_string_returns_early():
    course = types.SimpleNamespace(htaccess_template="")
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        m.assert_not_called()


def test_generate_htaccess_formats_userlist_commas():
    course = types.SimpleNamespace(
        htaccess_template="{userlist_commas}|{userlist_spaces}|{userlist_quotes_spaces}",
        instructors=[{"webaccount": "alice"}, {"webaccount": "bob"}],
        targetdir_i="/build/instructor",
    )
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        content = m.call_args[0][1]
    assert "alice,bob" in content


def test_generate_htaccess_formats_userlist_spaces():
    course = types.SimpleNamespace(
        htaccess_template="{userlist_commas}|{userlist_spaces}|{userlist_quotes_spaces}",
        instructors=[{"webaccount": "alice"}, {"webaccount": "bob"}],
        targetdir_i="/build/instructor",
    )
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        content = m.call_args[0][1]
    assert "alice bob" in content


def test_generate_htaccess_formats_quoted_spaces():
    course = types.SimpleNamespace(
        htaccess_template="{userlist_commas}|{userlist_spaces}|{userlist_quotes_spaces}",
        instructors=[{"webaccount": "alice"}, {"webaccount": "bob"}],
        targetdir_i="/build/instructor",
    )
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        content = m.call_args[0][1]
    assert '"alice"' in content
    assert '"bob"' in content


def test_generate_htaccess_writes_to_targetdir_i():
    course = types.SimpleNamespace(
        htaccess_template="{userlist_commas}|{userlist_spaces}|{userlist_quotes_spaces}",
        instructors=[{"webaccount": "alice"}],
        targetdir_i="/build/instructor",
    )
    with mock.patch("base.spit") as m:
        author.generate_htaccess(course)
        filepath = m.call_args[0][0]
    assert filepath == os.path.join("/build/instructor", c.HTACCESS_FILE)


# ── prepare_itree_zip ─────────────────────────────────────────────────────────

def test_prepare_itree_zip_no_itreedir_returns_early():
    course = types.SimpleNamespace(itreedir=None, directory=mock.MagicMock())
    author.prepare_itree_zip(course)
    course.directory.make_the.assert_not_called()


def test_prepare_itree_zip_non_zip_raises():
    course = types.SimpleNamespace(itreedir="mydir_not_zip", directory=mock.MagicMock())
    with pytest.raises(b.CritialError):
        author.prepare_itree_zip(course)


def test_prepare_itree_zip_valid_zip_calls_make_the_twice():
    course = types.SimpleNamespace(itreedir="content.zip", directory=mock.MagicMock())
    author.prepare_itree_zip(course)
    assert course.directory.make_the.call_count == 2


# ── purge_all_but ─────────────────────────────────────────────────────────────

def test_purge_all_but_deletes_unlisted_file(tmp_path):
    (tmp_path / "delete_me.html").write_text("x")
    (tmp_path / "keep.html").write_text("x")
    author.purge_all_but(str(tmp_path), {"keep.html"})
    assert not (tmp_path / "delete_me.html").exists()
    assert (tmp_path / "keep.html").exists()


def test_purge_all_but_keeps_all_listed_files(tmp_path):
    (tmp_path / "a.html").write_text("x")
    (tmp_path / "b.html").write_text("x")
    author.purge_all_but(str(tmp_path), {"a.html", "b.html"})
    assert (tmp_path / "a.html").exists()
    assert (tmp_path / "b.html").exists()


def test_purge_all_but_respects_exception_prefix(tmp_path):
    (tmp_path / ".sedrila_cache_abc").write_text("x")
    author.purge_all_but(str(tmp_path), set(), exception=".sedrila_cache")
    assert (tmp_path / ".sedrila_cache_abc").exists()


def test_purge_all_but_non_exception_file_still_deleted(tmp_path):
    (tmp_path / ".sedrila_cache_abc").write_text("x")
    (tmp_path / "other.html").write_text("x")
    author.purge_all_but(str(tmp_path), set(), exception=".sedrila_cache")
    assert not (tmp_path / "other.html").exists()


def test_purge_all_but_empty_dir_is_noop(tmp_path):
    author.purge_all_but(str(tmp_path), set())  # must not raise


# ── prepare_directories ───────────────────────────────────────────────────────

def test_prepare_directories_creates_missing_targetdir(tmp_path):
    ts = str(tmp_path / "new_build")
    ti = str(tmp_path / "new_build" / c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
    author.prepare_directories(ts, ti)
    assert os.path.isdir(ts)
    assert os.path.isdir(ti)


def test_prepare_directories_creates_targetdir_i_if_missing(tmp_path):
    ts = tmp_path / "build"
    ts.mkdir()
    ti = str(ts / c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
    author.prepare_directories(str(ts), ti)
    assert os.path.isdir(ti)


def test_prepare_directories_nonempty_without_metadata_raises(tmp_path):
    ts = tmp_path / "build"
    ts.mkdir()
    (ts / "file1.html").write_text("x")
    (ts / "file2.html").write_text("x")  # len > 1 → "not_empty"
    ti = str(ts / c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
    with pytest.raises(b.CritialError):
        author.prepare_directories(str(ts), ti)


def test_prepare_directories_nonempty_with_metadata_is_ok(tmp_path):
    ts = tmp_path / "build"
    ts.mkdir()
    (ts / c.METADATA_FILE).write_text("{}")
    (ts / "page.html").write_text("x")
    ti = str(ts / c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
    author.prepare_directories(str(ts), ti)  # must not raise
    assert os.path.isdir(ti)
