"""Unit tests for sdrl/subcmd/server.py."""
import argparse
import http.server
import unittest.mock as mock

import pytest

import sdrl.subcmd.server as server


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_subparser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sp = sub.add_parser("server")
    server.add_arguments(sp)
    return sp


# ── add_arguments ─────────────────────────────────────────────────────────────

def test_add_arguments_port_and_sourcedir():
    args = _make_subparser().parse_args(["8080", "/tmp/mydir"])
    assert args.port == 8080
    assert args.sourcedir == "/tmp/mydir"
    assert args.quiet is False


def test_add_arguments_port_is_int():
    args = _make_subparser().parse_args(["9000", "/tmp/mydir"])
    assert isinstance(args.port, int)


def test_add_arguments_quiet_short_flag():
    args = _make_subparser().parse_args(["-q", "8080", "/tmp/mydir"])
    assert args.quiet is True


def test_add_arguments_quiet_long_flag():
    args = _make_subparser().parse_args(["--quiet", "8080", "/tmp/mydir"])
    assert args.quiet is True


def test_add_arguments_non_integer_port_fails():
    with pytest.raises(SystemExit):
        _make_subparser().parse_args(["notaport", "/tmp/mydir"])


# ── QuietHandler.do_GET ───────────────────────────────────────────────────────

def _make_handler() -> server.QuietHandler:
    """Create a QuietHandler without initialising the socket machinery."""
    return server.QuietHandler.__new__(server.QuietHandler)


def test_quiet_handler_suppresses_broken_pipe():
    with mock.patch.object(http.server.SimpleHTTPRequestHandler, 'do_GET',
                           side_effect=BrokenPipeError):
        handler = _make_handler()
        handler.do_GET()  # must not raise


def test_quiet_handler_suppresses_connection_reset():
    with mock.patch.object(http.server.SimpleHTTPRequestHandler, 'do_GET',
                           side_effect=ConnectionResetError):
        handler = _make_handler()
        handler.do_GET()  # must not raise


def test_quiet_handler_propagates_other_exceptions():
    with mock.patch.object(http.server.SimpleHTTPRequestHandler, 'do_GET',
                           side_effect=RuntimeError("unexpected")):
        handler = _make_handler()
        with pytest.raises(RuntimeError):
            handler.do_GET()


def test_quiet_handler_normal_call_delegates_to_parent():
    call_log = []
    with mock.patch.object(http.server.SimpleHTTPRequestHandler, 'do_GET',
                           side_effect=lambda: call_log.append("called")):
        handler = _make_handler()
        handler.do_GET()
    assert call_log == ["called"]


# ── constants ─────────────────────────────────────────────────────────────────

def test_localhost_only_is_loopback():
    assert server.LOCALHOST_ONLY == '127.0.0.1'
