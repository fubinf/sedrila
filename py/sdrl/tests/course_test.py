# pytest tests
import re

import sdrl.course
import sdrl.markdown as md

def test_macros():
    expansion = md.render_markdown("difficult [DIFF::4] morestuff")
    print(expansion)
    assert re.search(r"difficult.+Difficulty: high", expansion)