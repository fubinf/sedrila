# pytest tests

import base as b
import sdrl.markdown as md


def render(markup: str) -> str:
    md.md.mode = b.Mode.INSTRUCTOR
    md.md.context_sourcefile = "nofile"
    md.md.partname = "nopart"
    return md.md.reset().convert(markup)


def test_perhaps_suppress_instructorinfo():
    md.md.mode = b.Mode.STUDENT  # turns on the suppression
    markup = "one [INSTRUCTOR::my heading] two [ENDINSTRUCTOR] three"
    output = "one  three"
    assert md.SedrilaPreprocessor(md.md).perhaps_suppress_instructorinfo(markup) == output
    

def test_keep_htmltags():
    markup = "_italic_ <div>somediv</div> **bold**"
    output = "<p><em>italic</em> <div>somediv</div> <strong>bold</strong></p>"
    assert render(markup) == output


def test_keep_greaterthan_lessthan():
    markup = "a < b and `b > c`"
    output = "<p>a &lt; b and <code>b &gt; c</code></p>"
    assert render(markup) == output


def test_verbatim_html_charescapes_yet_keep_free_ampersands():
    markup = "&lt; Meier & Söhne"
    output = "<p>&lt; Meier &amp; Söhne</p>"
    assert render(markup) == output
