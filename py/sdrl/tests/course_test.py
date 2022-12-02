# pytest tests
import re

import sdrl.course
import sdrl.markdown as md

def test_macros(capsys):
    expansion = md.render_markdown("(none)", "difficult [DIFF::4] morestuff")
    print(expansion)
    assert re.search(r"difficult.+Difficulty: high", expansion)