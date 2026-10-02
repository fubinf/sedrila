import sys

import pytest

import sedrila.base.base as b
import sedrila.__main__ as sedrila_main


def setup_function():
    b._testmode_reset()


def test_main_raises_on_windows(monkeypatch):
    """main() calls b.critical() when running on Windows."""
    monkeypatch.setattr(sys, 'platform', 'win32')
    with pytest.raises(b.CritialError, match="Windows"):
        sedrila_main.main()
