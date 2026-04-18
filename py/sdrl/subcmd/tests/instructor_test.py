"""Unit tests for sdrl/subcmd/instructor.py."""
import argparse
import logging
import types
import unittest.mock as mock

import pytest

import base as b
import sdrl.webapp
import sdrl.subcmd.instructor as instructor


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.ERROR


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_subparser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sp = sub.add_parser('instructor')
    instructor.add_arguments(sp)
    return sp


# ── add_arguments ─────────────────────────────────────────────────────────────

def test_add_arguments_defaults():
    args = _make_subparser().parse_args([])
    assert args.workdir == []
    assert args.op == ""
    assert args.log == "INFO"
    assert args.port == int(sdrl.webapp.DEFAULT_PORT)


def test_add_arguments_workdir_single():
    args = _make_subparser().parse_args(["mydir"])
    assert args.workdir == ["mydir"]


def test_add_arguments_workdir_multiple():
    args = _make_subparser().parse_args(["dir1", "dir2"])
    assert args.workdir == ["dir1", "dir2"]


def test_add_arguments_op_webapp():
    args = _make_subparser().parse_args(['--op', 'webapp'])
    assert args.op == 'webapp'


def test_add_arguments_op_edit():
    args = _make_subparser().parse_args(['--op', 'edit'])
    assert args.op == 'edit'


def test_add_arguments_op_commit_and_push():
    args = _make_subparser().parse_args(['--op', 'commit_and_push'])
    assert args.op == 'commit_and_push'


def test_add_arguments_invalid_op_fails():
    with pytest.raises(SystemExit):
        _make_subparser().parse_args(['--op', "nonexistent"])


def test_add_arguments_port_short():
    args = _make_subparser().parse_args(['-p', "9090"])
    assert args.port == 9090


def test_add_arguments_port_long():
    args = _make_subparser().parse_args(['--port', "8888"])
    assert args.port == 8888


# ── execute: no workdir raises ────────────────────────────────────────────────

def test_execute_no_workdir_raises():
    pargs = types.SimpleNamespace(log='ERROR', workdir=[])
    with pytest.raises(b.CritialError):
        instructor.execute(pargs)


# ── OP_CMDS / MENU_CMDS completeness ─────────────────────────────────────────

def test_op_cmds_contains_expected_keys():
    assert set(instructor.OP_CMDS.keys()) == {'webapp', 'edit', 'commit_and_push'}


def test_menu_cmds_contains_expected_keys():
    assert set(instructor.MENU_CMDS.keys()) == {'v', 'w', 'e', 'c'}
