"""Unit tests for sdrl/subcmd/maintainer.py."""
import argparse
import logging
import types
import unittest.mock as mock

import pytest

import base as b
import sdrl.constants as c
import sdrl.subcmd.maintainer as maintainer


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

def make_task(name, sourcefile, to_be_skipped=False):
    return types.SimpleNamespace(name=name, sourcefile=sourcefile, to_be_skipped=to_be_skipped)


def make_taskgroup(name, sourcefile, tasks, to_be_skipped=False):
    return types.SimpleNamespace(
        name=name, sourcefile=sourcefile, tasks=tasks, to_be_skipped=to_be_skipped
    )


def make_chapter(name, taskgroups, to_be_skipped=False):
    return types.SimpleNamespace(name=name, taskgroups=taskgroups, to_be_skipped=to_be_skipped)


def make_course(chapters, altdir=None, chapterdir="/course/ch"):
    return types.SimpleNamespace(chapters=chapters, altdir=altdir, chapterdir=chapterdir)


def _make_subparser(cmd="maintainer"):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sp = sub.add_parser(cmd)
    maintainer.add_arguments(sp)
    return sp


# ── add_arguments ─────────────────────────────────────────────────────────────

def test_add_arguments_defaults():
    sp = _make_subparser()
    args = sp.parse_args([])
    assert args.config == c.AUTHOR_CONFIG_FILENAME
    assert args.log == "INFO"
    assert args.include_stage == "draft"
    assert args.check_links is None
    assert args.check_programs is False
    assert args.collect is False
    assert args.batch is False
    assert args.targetdir is None
    assert args.output is None


def test_add_arguments_check_links_no_arg_is_all():
    sp = _make_subparser()
    args = sp.parse_args(["--check-links"])
    assert args.check_links == "all"


def test_add_arguments_check_links_with_file():
    sp = _make_subparser()
    args = sp.parse_args(["--check-links", "some/file.md"])
    assert args.check_links == "some/file.md"


def test_add_arguments_check_programs_flag():
    sp = _make_subparser()
    args = sp.parse_args(["--check-programs"])
    assert args.check_programs is True


def test_add_arguments_collect_flag():
    sp = _make_subparser()
    args = sp.parse_args(["--collect"])
    assert args.collect is True


def test_add_arguments_batch_flag():
    sp = _make_subparser()
    args = sp.parse_args(["--batch"])
    assert args.batch is True


def test_add_arguments_output_file():
    sp = _make_subparser()
    args = sp.parse_args(["-o", "out.json"])
    assert args.output == "out.json"


def test_add_arguments_include_stage():
    sp = _make_subparser()
    args = sp.parse_args(["--include-stage", "beta"])
    assert args.include_stage == "beta"


# ── execute dispatch ──────────────────────────────────────────────────────────

def _make_pargs(**kwargs):
    defaults = dict(log="INFO", collect=False, check_links=None, check_programs=False)
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_execute_dispatches_to_collect():
    pargs = _make_pargs(collect=True)
    with mock.patch.object(maintainer, "collect_command") as m:
        maintainer.execute(pargs)
        m.assert_called_once_with(pargs)


def test_execute_dispatches_to_check_links():
    pargs = _make_pargs(check_links="all")
    with mock.patch.object(maintainer, "check_links_command") as m:
        maintainer.execute(pargs)
        m.assert_called_once_with(pargs)


def test_execute_dispatches_to_check_programs():
    pargs = _make_pargs(check_programs=True)
    with mock.patch.object(maintainer, "check_programs_command") as m:
        maintainer.execute(pargs)
        m.assert_called_once_with(pargs)


def test_execute_collect_takes_priority_over_check_links():
    """collect is checked first in execute."""
    pargs = _make_pargs(collect=True, check_links="all")
    with mock.patch.object(maintainer, "collect_command") as collect_m:
        with mock.patch.object(maintainer, "check_links_command") as links_m:
            maintainer.execute(pargs)
            collect_m.assert_called_once()
            links_m.assert_not_called()


def test_execute_no_command_emits_error():
    b.loglevel = logging.ERROR
    pargs = _make_pargs()
    maintainer.execute(pargs)
    assert b.num_errors == 1


# ── extract_markdown_files_from_course ────────────────────────────────────────

def test_extract_skips_skipped_chapter():
    ch = make_chapter("ch1", taskgroups=[], to_be_skipped=True)
    course = make_course([ch])
    result = maintainer.extract_markdown_files_from_course(course)
    assert result == []


def test_extract_skips_skipped_taskgroup():
    tg = make_taskgroup("tg1", "/course/ch/ch1/tg1/index.md", tasks=[], to_be_skipped=True)
    ch = make_chapter("ch1", taskgroups=[tg])
    course = make_course([ch])
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.extract_markdown_files_from_course(course)
    assert result == []


def test_extract_includes_taskgroup_sourcefile_when_exists():
    tg = make_taskgroup("tg1", "/course/ch/ch1/tg1/index.md", tasks=[])
    ch = make_chapter("ch1", taskgroups=[tg])
    course = make_course([ch])
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.extract_markdown_files_from_course(course)
    assert "/course/ch/ch1/tg1/index.md" in result


def test_extract_excludes_taskgroup_sourcefile_when_not_exists():
    tg = make_taskgroup("tg1", "/course/ch/ch1/tg1/index.md", tasks=[])
    ch = make_chapter("ch1", taskgroups=[tg])
    course = make_course([ch])
    with mock.patch("os.path.exists", return_value=False):
        result = maintainer.extract_markdown_files_from_course(course)
    assert result == []


def test_extract_includes_task_sourcefile():
    task = make_task("t1", "/course/ch/ch1/tg1/t1.md")
    tg = make_taskgroup("tg1", "/course/ch/ch1/tg1/index.md", tasks=[task])
    ch = make_chapter("ch1", taskgroups=[tg])
    course = make_course([ch])
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.extract_markdown_files_from_course(course)
    assert "/course/ch/ch1/tg1/t1.md" in result


def test_extract_skips_skipped_task():
    task = make_task("t1", "/course/ch/ch1/tg1/t1.md", to_be_skipped=True)
    tg = make_taskgroup("tg1", "/course/ch/ch1/tg1/index.md", tasks=[task])
    ch = make_chapter("ch1", taskgroups=[tg])
    course = make_course([ch])
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.extract_markdown_files_from_course(course)
    assert "/course/ch/ch1/tg1/t1.md" not in result


# ── find_markdown_files ───────────────────────────────────────────────────────

def test_find_markdown_files_no_altdir():
    course = make_course(chapters=[], altdir=None, chapterdir="/course/ch")
    with mock.patch.object(maintainer, "extract_markdown_files_from_course", return_value=["/f1.md"]):
        result = maintainer.find_markdown_files(course)
    assert result == ["/f1.md"]


def test_find_markdown_files_altdir_not_a_dir():
    course = make_course(chapters=[], altdir="/no/such/dir", chapterdir="/course/ch")
    with mock.patch.object(maintainer, "extract_markdown_files_from_course", return_value=["/f1.md"]):
        with mock.patch("os.path.isdir", return_value=False):
            result = maintainer.find_markdown_files(course)
    assert result == ["/f1.md"]


def test_find_markdown_files_calls_add_altdir_when_altdir_exists():
    course = make_course(chapters=[], altdir="/alt/ch", chapterdir="/course/ch")
    base_files = ["/course/ch/ch1/t1.md"]
    expected = base_files + ["/alt/ch/ch1/t1.md"]
    with mock.patch.object(maintainer, "extract_markdown_files_from_course", return_value=base_files):
        with mock.patch("os.path.isdir", return_value=True):
            with mock.patch.object(maintainer, "add_altdir_files", return_value=expected) as m:
                result = maintainer.find_markdown_files(course)
                m.assert_called_once_with(base_files, "/course/ch", "/alt/ch")
    assert result == expected


# ── add_altdir_files ──────────────────────────────────────────────────────────

def test_add_altdir_files_adds_existing_alt_file():
    files = ["/course/ch/ch1/t1.md"]
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.add_altdir_files(files, "/course/ch", "/alt/ch")
    assert "/alt/ch/ch1/t1.md" in result


def test_add_altdir_files_skips_nonexistent_alt_file():
    files = ["/course/ch/ch1/t1.md"]
    with mock.patch("os.path.exists", return_value=False):
        result = maintainer.add_altdir_files(files, "/course/ch", "/alt/ch")
    assert result == files


def test_add_altdir_files_no_duplicates():
    files = ["/course/ch/ch1/t1.md", "/alt/ch/ch1/t1.md"]  # already contains alt file
    with mock.patch("os.path.exists", return_value=True):
        result = maintainer.add_altdir_files(files, "/course/ch", "/alt/ch")
    assert result.count("/alt/ch/ch1/t1.md") == 1


def test_add_altdir_files_preserves_original_files():
    files = ["/course/ch/ch1/t1.md"]
    with mock.patch("os.path.exists", return_value=False):
        result = maintainer.add_altdir_files(files, "/course/ch", "/alt/ch")
    assert "/course/ch/ch1/t1.md" in result


def test_add_altdir_files_empty_input():
    result = maintainer.add_altdir_files([], "/course/ch", "/alt/ch")
    assert result == []
