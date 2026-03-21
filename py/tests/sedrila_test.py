import sys
import unittest.mock as mock

import pytest

import base as b
import sedrila


def setup_function():
    b._testmode_reset()


def test_main_raises_on_windows(monkeypatch):
    """main() calls b.critical() when running on Windows."""
    monkeypatch.setattr(sys, 'platform', 'win32')
    with pytest.raises(b.CritialError, match="Windows"):
        sedrila.main()


def test_main_swallows_critical_error_from_subcommand(monkeypatch):
    """CritialError raised by execute_subcommand is silently caught."""
    monkeypatch.setattr(sys, 'platform', 'linux')

    fake_parser = mock.MagicMock()
    fake_parser.parse_args.return_value = mock.MagicMock()
    fake_parser.execute_subcommand.side_effect = b.CritialError("boom")

    with mock.patch('sdrl.argparser.SedrilaArgParser', return_value=fake_parser):
        sedrila.main()  # must not raise


def test_main_calls_execute_subcommand(monkeypatch):
    """main() parses args and hands them to execute_subcommand."""
    monkeypatch.setattr(sys, 'platform', 'linux')

    fake_args = mock.MagicMock()
    fake_parser = mock.MagicMock()
    fake_parser.parse_args.return_value = fake_args

    with mock.patch('sdrl.argparser.SedrilaArgParser', return_value=fake_parser):
        sedrila.main()

    fake_parser.scan.assert_called_once_with("sdrl.subcmd.*")
    fake_parser.parse_args.assert_called_once()
    fake_parser.execute_subcommand.assert_called_once_with(fake_args)
