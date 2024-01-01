# pytest tests
import re

import base
import sdrl.course
import sdrl.markdown as md

def test_macros(capsys):
    md.register_macro('DIFF', 1, sdrl.course.Task.expand_diff)
    expansion = md.render_markdown("(none)", "difficult [DIFF::4] morestuff", 
                                   mode=base.Mode.STUDENT, blockmacro_topmatter=dict())
    print(expansion)
    assert re.search(r"difficult.+Difficulty: high", expansion)
    md.render_markdown("(none)", "[DIFF::44]", 
                       mode=base.Mode.STUDENT, blockmacro_topmatter=dict())  # non-existing level
    assert "in range" in capsys.readouterr().out
