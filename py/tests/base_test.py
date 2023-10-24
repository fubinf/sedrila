import logging

import base as b

def print_and_log():
    print("first")
    b.warning("a warning")
    print("second")


def test_logging_on(capsys):
    b.loglevel = logging.WARNING
    print_and_log()
    out, err = capsys.readouterr()
    assert out == "first\na warning\nsecond\n"


def test_logging_off(capsys):
    b.loglevel = logging.ERROR
    print_and_log()
    out, err = capsys.readouterr()
    assert out == "first\nsecond\n"
