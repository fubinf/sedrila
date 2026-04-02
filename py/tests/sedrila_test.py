import sys

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
