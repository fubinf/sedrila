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


def test_problem_with_path():
    assert b.problem_with_path("filename.suff") == ""
    assert b.problem_with_path(".invisible_file") == ""
    assert b.problem_with_path("relative/path/to/file.md") == ""
    assert b.problem_with_path("name$with!strange_chars.allowed") == ""
    assert b.problem_with_path("/root") == "Error: path '/root' is an absolute path"
    assert b.problem_with_path("../sisterdir") == "Error: path '../sisterdir' must not contain '..'"
    assert b.problem_with_path("cannot:colon") == "Error: path 'cannot:colon' contains forbidden character ':'"


def test_validate_dict_unsurprisingness(capsys):
    b._testmode_reset()
    b.loglevel = logging.WARNING
    illegal_data = {
        "key\nname": "value",  # control char in key
        "valid": "bad\x08value"  # control char in value
    }
    valid_data = {"valid_key": "valid_value"}
    b.validate_dict_unsurprisingness("mysource.file", illegal_data)
    out, err = capsys.readouterr()
    assert "control chars not allowed: 'key\\nname" in out
    assert "control chars not allowed: 'valid: bad\\x08value'" in out
    b.validate_dict_unsurprisingness("mysource.file", valid_data)
    out, err = capsys.readouterr()
    assert out == ""  # no warnings for valid data
