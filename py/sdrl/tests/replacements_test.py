import logging
import pytest

import base as b
import sdrl.replacements as r


@pytest.fixture(autouse=True)
def reset_state():
    """Reset module state before each test."""
    r.replacementsdict = {}
    r.replacements_loaded = False
    b._testmode_reset()
    b.loglevel = logging.WARNING


# ------------------------
# Load tests
# ------------------------

def test_load_single_replacement():
    r.load_replacements_string("test.html", "<replacement id='foo'>bar</replacement>")
    assert r.replacementsdict == {"foo": "bar"}
    assert r.replacements_loaded


def test_load_multiple_replacements():
    s = """
    <replacement id='a'>value_a</replacement>

    <replacement id="b">value_b</replacement>
    """
    r.load_replacements_string("test.html", s)
    assert r.replacementsdict["a"] == "value_a"
    assert r.replacementsdict["b"] == "value_b"


def test_load_multiline_body():
    s = "<replacement id='multi'>line1\nline2\nline3</replacement>"
    r.load_replacements_string("test.html", s)
    assert r.replacementsdict["multi"] == "line1\nline2\nline3"


def test_load_double_quoted_id():
    r.load_replacements_string("test.html", '<replacement id="dq">content</replacement>')
    assert "dq" in r.replacementsdict


def test_load_hyphen_underscore_in_id():
    r.load_replacements_string("test.html", "<replacement id='my-id_1'>x</replacement>")
    assert "my-id_1" in r.replacementsdict


def test_load_whitespace_variations():
    s = "<replacement    id='x'   >y</replacement>"
    r.load_replacements_string("test.html", s)
    assert r.replacementsdict["x"] == "y"


def test_duplicate_id_emits_warning(capsys):
    s = (
        "<replacement id='dup'>first</replacement>"
        "<replacement id='dup'>second</replacement>"
    )
    r.load_replacements_string("test.html", s)

    out, _ = capsys.readouterr()
    assert "dup" in out
    assert r.replacementsdict["dup"] == "second"  # last wins


def test_load_sets_replacements_loaded_even_if_empty():
    r.load_replacements_string("test.html", "no replacements here")
    assert r.replacements_loaded
    assert r.replacementsdict == {}


# ------------------------
# Get tests
# ------------------------

def test_get_replacement_before_load():
    result = r.get_replacement("ctx.html", "original content", "any_id")
    assert result == "original content"


def test_get_replacement_known_id():
    r.load_replacements_string("test.html", "<replacement id='greet'>Hello</replacement>")
    result = r.get_replacement("ctx.html", "ignored", "greet")
    assert result == "Hello"


def test_get_replacement_unknown_id_returns_fallback(capsys):
    r.load_replacements_string("test.html", "<replacement id='x'>X</replacement>")
    result = r.get_replacement("ctx.html", "ignored", "missing")

    assert result == "????"
    out, _ = capsys.readouterr()
    assert "missing" in out


def test_get_replacement_unknown_id_emits_warning(capsys):
    r.load_replacements_string("test.html", "")  # marks as loaded

    r.get_replacement("ctx.html", "content", "no_such_id")

    out, _ = capsys.readouterr()
    assert "no_such_id" in out