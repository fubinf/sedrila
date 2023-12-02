# pytest tests
import re

import sdrl.course
import sdrl.markdown as md

def test_macros(capsys):
    expansion = md.render_markdown("(none)", "difficult [DIFF::4] morestuff", 
                                   mode="-", blockmacro_topmatter=dict())
    print(expansion)
    assert re.search(r"difficult.+Difficulty: high", expansion)
    md.render_markdown("(none)", "[DIFF::44]", 
                       mode="-", blockmacro_topmatter=dict())  # non-existing level
    assert "in range" in capsys.readouterr().out
