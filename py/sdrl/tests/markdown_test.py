# pytest tests

import sdrl.markdown as md

def expander(name, arg1, arg2):
    return f"{name}({arg1},{arg2})"


def test_expand_macros():
    md.macrodefs = dict()
    md.register_macros(macros=[('A', 0), ('B', 1), ('C', 2)], expander=expander)
    assert md.expand_macros("a [A], b [B::argb], c [C::c1::c2], d") == "a A(None,None), b B(argb,None), c C(c1,c2), d" 
    

def test_expand_nonexisting_macro(capsys):
    md.macrodefs = dict()
    md.register_macros(macros=[('A', 0)], expander=expander)
    assert md.expand_macros("[ABC]") == "[ABC]"
    out, err = capsys.readouterr()
    assert "not defined" in out


def test_expand_macro_with_wrong_args(capsys):
    md.macrodefs = dict()
    md.register_macros(macros=[('A', 0), ('B', 1), ('C', 2)], expander=expander)
    assert md.expand_macros("[A::onearg][B::two::args][C]") == "[A::onearg][B::two::args][C]"
    log_out, err = capsys.readouterr()
    assert "expects 0" in log_out 
    assert "expects 1" in log_out
    assert "expects 2" in log_out