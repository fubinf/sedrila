# pytest tests
import re

import base
import sdrl.course
import sdrl.macros as macros
import sdrl.markdown as md

def test_macros(capsys):
    macros.register_macro('DIFF', 1, sdrl.course.Task.expand_diff)
    expansion = md.render_markdown("(none)", "dummypart", 
                                   "difficult [DIFF::4] morestuff", 
                                   mode=base.Mode.STUDENT, blockmacro_topmatter=dict())
    print(expansion)
    assert re.search(r"difficult.+Difficulty: high", expansion)
    md.render_markdown("(none)", "dummypart2", 
                       "[DIFF::44]", 
                       mode=base.Mode.STUDENT, blockmacro_topmatter=dict())  # non-existing level
    assert "in range" in capsys.readouterr().out
