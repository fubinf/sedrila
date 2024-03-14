# pytest tests
import pytest

import base as b
import sdrl.markdown as md
import sdrl.macros as macros

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


@pytest.mark.parametrize(
    ['layout','markup','output'], [
        ['layout1',
         'text\n[END]\n[START]\ntext',
         '<p>text\n[END]\n[START]\ntext</p>',
        ],
        ['layout2',
         'text\n[END]\n\n[START]\ntext',
         '<p>text\n</p>[END]\n[START]<p>\ntext</p>',
         ],
        ['layout3',
         'text\n\n[END]\n[START]\n\ntext',
         '<p>text</p>\n[END]\n[START]\n<p>text</p>',
         ],
        ['layout4',
         'text\n\n[END]\n\n[START]\n\ntext',
         '<p>text</p>\n[END]\n[START]\n<p>text</p>',
         ],
    ])
def test_macrocall(layout, markup, output):
    def expander(macrocall: macros.Macrocall):
        return f"{macrocall.macrocall_text}"

    macros._testmode_reset()
    macros.register_macro('START', 0, macros.MM.BLOCKSTART, expander)
    macros.register_macro('END', 0, macros.MM.BLOCKEND, expander)
    rendered = render(markup)
    print("##", layout)
    print("    markup input:\n", markup, sep="")
    print("    should out:\n", output, sep="")
    print("    actual out:\n", rendered, sep="")
    assert rendered == output


def test_html_charescapes_and_free_ampersands():
    markup = "&lt; Meier & Söhne , `&lt; Meier & Söhne`"
    output = "<p>&lt; Meier &amp; Söhne , <code>&amp;lt; Meier &amp; Söhne</code></p>"
    assert render(markup) == output
