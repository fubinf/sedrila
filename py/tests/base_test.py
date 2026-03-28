import logging
import os

import pytest

import base as b


# ── helpers ──────────────────────────────────────────────────────────────────

def setup_function():
    """Reset global state before every test."""
    b._testmode_reset()
    b.loglevel = logging.WARNING
    b.suppress_msg_duplicates(False)


# ── existing tests ────────────────────────────────────────────────────────────

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


def test_expandvars():
    vars = {"HOME": "/home/user", "NAME": "Alice", "COUNT": "3"}
    # ----- basic substitution: $VAR and ${VAR} forms
    assert b.expandvars("hello $NAME", vars) == "hello Alice"
    assert b.expandvars("hello ${NAME}", vars) == "hello Alice"
    # ----- multiple variables in one string
    assert b.expandvars("$NAME lives in $HOME", vars) == "Alice lives in /home/user"
    # ----- mixed forms
    assert b.expandvars("${NAME} has $COUNT items in $HOME", vars) == "Alice has 3 items in /home/user"
    # ----- no variables at all
    assert b.expandvars("plain text", vars) == "plain text"
    # ----- empty string
    assert b.expandvars("", vars) == ""
    # ----- adjacent variables
    assert b.expandvars("$NAME$COUNT", vars) == "Alice3"
    assert b.expandvars("${NAME}${COUNT}", vars) == "Alice3"
    # ----- variable at start and end
    assert b.expandvars("$NAME!", vars) == "Alice!"
    # ----- dollar sign not followed by word char is left alone
    assert b.expandvars("price is $", vars) == "price is $"
    assert b.expandvars("a $ b", vars) == "a $ b"
    # ----- empty vars dict: no variables defined, none referenced
    assert b.expandvars("no vars here", {}) == "no vars here"
    # ----- missing variables raise ExpansionException with sorted list
    with pytest.raises(b.ExpansionException) as exc_info:
        b.expandvars("$MISSING and ${ALSO_MISSING}", vars)
    assert exc_info.value.missing == ["ALSO_MISSING", "MISSING"]
    # ----- mix of found and missing
    with pytest.raises(b.ExpansionException) as exc_info:
        b.expandvars("$NAME and $UNKNOWN", vars)
    assert exc_info.value.missing == ["UNKNOWN"]
    # ----- single missing variable
    with pytest.raises(b.ExpansionException) as exc_info:
        b.expandvars("${NOPE}", vars)
    assert exc_info.value.missing == ["NOPE"]


# ── as_fingerprint ────────────────────────────────────────────────────────────

def test_as_fingerprint_removes_spaces_and_lowercases():
    assert b.as_fingerprint("ABCD 1234 EFGH") == "abcd1234efgh"
    assert b.as_fingerprint("abcd1234") == "abcd1234"
    assert b.as_fingerprint("AB CD EF GH") == "abcdefgh"
    assert b.as_fingerprint("2868 1080 B8B2 E25B") == "286810 80b8b2e25b".replace(" ", "")


# ── slugify ───────────────────────────────────────────────────────────────────

def test_slugify():
    assert b.slugify("Hello World") == "hello-world"
    assert b.slugify("already-slugified") == "already-slugified"
    assert b.slugify("multiple   spaces") == "multiple-spaces"
    assert b.slugify("Café & Co.") == "café-co"
    assert b.slugify("  leading trailing  ") == "leading-trailing"


# ── plural_s ──────────────────────────────────────────────────────────────────

def test_plural_s():
    assert b.plural_s(0) == "s"
    assert b.plural_s(1) == ""
    assert b.plural_s(2) == "s"
    assert b.plural_s(1, "en") == ""
    assert b.plural_s(2, "en") == "en"


# ── set_loglevel ──────────────────────────────────────────────────────────────

def test_set_loglevel_known_levels():
    b.set_loglevel("DEBUG")
    assert b.loglevel == logging.DEBUG
    b.set_loglevel("INFO")
    assert b.loglevel == logging.INFO
    b.set_loglevel("ERROR")
    assert b.loglevel == logging.ERROR


def test_set_loglevel_unknown_is_ignored():
    b.set_loglevel("WARNING")
    b.set_loglevel("NONEXISTENT")
    assert b.loglevel == logging.WARNING  # unchanged


# ── error / critical / num_errors ─────────────────────────────────────────────

def test_error_increments_num_errors():
    assert b.num_errors == 0
    b.error("an error")
    assert b.num_errors == 1
    b.error("another error")
    assert b.num_errors == 2


def test_critical_raises():
    with pytest.raises(b.CritialError, match="something went wrong"):
        b.critical("something went wrong")


def test_critical_increments_num_errors():
    with pytest.raises(b.CritialError):
        b.critical("boom")
    assert b.num_errors == 1


# ── suppress_msg_duplicates ───────────────────────────────────────────────────

def test_suppress_msg_duplicates_suppresses(capsys):
    b.suppress_msg_duplicates(True)
    b.warning("duplicate message")
    b.warning("duplicate message")
    out, _ = capsys.readouterr()
    assert out.count("duplicate message") == 1


def test_suppress_msg_duplicates_off_allows_repeats(capsys):
    b.suppress_msg_duplicates(False)
    b.warning("repeated message")
    b.warning("repeated message")
    out, _ = capsys.readouterr()
    assert out.count("repeated message") == 2


# ── expandvars ────────────────────────────────────────────────────────────────

def test_expandvars_known_variable(capsys):
    os.environ["_SEDRILA_TEST_VAR"] = "hello"
    try:
        result = b.expandvars("$_SEDRILA_TEST_VAR world", "ctx")
        assert result == "hello world"
        out, _ = capsys.readouterr()
        assert out == ""  # no warning
    finally:
        del os.environ["_SEDRILA_TEST_VAR"]


def test_expandvars_undefined_variable_warns(capsys):
    os.environ.pop("_SEDRILA_UNDEFINED_XYZ", None)
    b.expandvars("$_SEDRILA_UNDEFINED_XYZ", "ctx")
    out, _ = capsys.readouterr()
    assert "env variable undefined" in out


# ── slurp / spit ─────────────────────────────────────────────────────────────

def test_slurp_spit_roundtrip(tmp_path):
    f = str(tmp_path / "test.txt")
    content = "hello\nwörld\n"
    b.spit(f, content)
    assert b.slurp(f) == content


def test_slurp_spit_bytes_roundtrip(tmp_path):
    f = str(tmp_path / "test.bin")
    content = b"\x00\x01\x02\xff"
    b.spit_bytes(f, content)
    assert b.slurp_bytes(f) == content


def test_slurp_spit_json_roundtrip(tmp_path):
    f = str(tmp_path / "test.json")
    data = {"key": "value", "num": 42}
    b.spit_json(f, data)
    assert b.slurp_json(f) == data


def test_slurp_spit_yaml_roundtrip(tmp_path):
    f = str(tmp_path / "test.yaml")
    data = {"key": "value", "list": [1, 2, 3]}
    b.spit_yaml(f, data)
    assert b.slurp_yaml(f) == data


# ── copyattrs ─────────────────────────────────────────────────────────────────

class _Target:
    pass


def test_copyattrs_mustcopy_present():
    t = _Target()
    b.copyattrs("ctx", {"a": 1, "b": "hello"}, t, "a,b", "", "")
    assert t.a == 1
    assert t.b == "hello"


def test_copyattrs_cancopy_present():
    t = _Target()
    b.copyattrs("ctx", {"required": 1, "optional": "yes"}, t, "required", "optional", "")
    assert t.required == 1
    assert t.optional == "yes"


def test_copyattrs_cancopy_absent_sets_none():
    t = _Target()
    b.copyattrs("ctx", {"required": 1}, t, "required", "optional", "")
    assert t.required == 1
    assert t.optional is None


def test_copyattrs_mustcopy_missing_raises():
    t = _Target()
    with pytest.raises(b.CritialError):
        b.copyattrs("ctx", {"a": 1}, t, "a,b", "", "")  # b is missing


def test_copyattrs_typecheck_wrong_type(capsys):
    t = _Target()
    b.copyattrs("ctx", {"num": "not-an-int"}, t, "num", "", "", typecheck={"num": int})
    out, _ = capsys.readouterr()
    assert "should be" in out


def test_copyattrs_none_source_uses_empty_dict():
    t = _Target()
    # None source should not crash — missing mustcopy raises as usual
    with pytest.raises(b.CritialError):
        b.copyattrs("ctx", None, t, "a", "", "")


def test_copyattrs_overwrite_false_warns(capsys):
    t = _Target()
    t.optional = "old"
    b.copyattrs("ctx", {"optional": "new"}, t, "", "optional", "", overwrite=False)
    out, _ = capsys.readouterr()
    assert "not overwriting" in out
    assert t.optional == "old"  # value unchanged


def test_copyattrs_report_extra_warns(capsys):
    t = _Target()
    b.copyattrs("ctx", {"known": 1, "unexpected": 2}, t, "known", "", "", report_extra=True)
    out, _ = capsys.readouterr()
    assert "unexpected extra attributes" in out


# ── slurp error paths ─────────────────────────────────────────────────────────

def test_slurp_nonexistent_file_raises():
    with pytest.raises(b.CritialError):
        b.slurp("/nonexistent/path/that/does/not/exist.txt")


# ── debug / info ──────────────────────────────────────────────────────────────

def test_debug_prints_when_loglevel_debug(capsys):
    b.loglevel = logging.DEBUG
    b.debug("debug message")
    out, _ = capsys.readouterr()
    assert "debug message" in out


def test_debug_silent_when_loglevel_info(capsys):
    b.loglevel = logging.INFO
    b.debug("debug message")
    out, _ = capsys.readouterr()
    assert out == ""


def test_info_prints_when_loglevel_info(capsys):
    b.loglevel = logging.INFO
    b.info("info message")
    out, _ = capsys.readouterr()
    assert "info message" in out


def test_info_silent_when_loglevel_warning(capsys):
    b.loglevel = logging.WARNING
    b.info("info message")
    out, _ = capsys.readouterr()
    assert out == ""


# ── finalmessage ──────────────────────────────────────────────────────────────

def test_finalmessage_no_errors_prints_timing(capsys):
    b.loglevel = logging.INFO
    assert b.num_errors == 0
    b.finalmessage()
    out, _ = capsys.readouterr()
    assert "seconds" in out


def test_finalmessage_with_errors_raises():
    b.error("an error")
    with pytest.raises(b.CritialError):
        b.finalmessage()


# ── caller ────────────────────────────────────────────────────────────────────

def test_caller_returns_function_and_lineno():
    result = b.caller(how_far_up=0)  # 0 = direct caller (this test function)
    assert "test_caller_returns_function_and_lineno" in result
    assert ":" in result


# ── _process_params with file and file2 ──────────────────────────────────────

def test_warning_with_file_and_file2(capsys):
    b.loglevel = logging.WARNING
    b.warning("something wrong", file="file1.md", file2="file2.md")
    out, _ = capsys.readouterr()
    assert "file1.md" in out
    assert "file2.md" in out
    assert "something wrong" in out
