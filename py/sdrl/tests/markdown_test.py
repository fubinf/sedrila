# pytest tests

import base as b
import sdrl.markdown as md

def expander(macrocall, name, arg1, arg2):
    return f"{name}({arg1},{arg2})"


def test_expand_macros():
    md.macrodefs = dict()
    md.register_macros(('MA', 0), ('MB', 1), ('MC', 2), expander=expander)
    assert md.expand_macros("-", "a [MA], b [MB::argb], c [MC::c1::c2], d") == "a MA(None,None), b MB(argb,None), c MC(c1,c2), d" 
    

def test_expand_nonexisting_macro(capsys):
    md.macrodefs = dict()
    md.register_macros(('MA', 0), expander=expander)
    assert md.expand_macros("-", "[MABC]") == "[MABC]"
    out, err = capsys.readouterr()
    assert "not defined" in out


def test_expand_macro_with_wrong_args(capsys):
    md.macrodefs = dict()
    md.register_macros(('MA', 0), ('MB', 1), ('MC', 2), expander=expander)
    assert md.expand_macros("(nofile)", "[MA::onearg][MB::two::args][MC]") == "[MA::onearg][MB::two::args][MC]"
    log_out, err = capsys.readouterr()
    assert "'(nofile)'" in log_out 
    assert "[MA::onearg]" in log_out 
    assert "expects 0" in log_out 
    assert "expects 1" in log_out
    assert "expects 2" in log_out
    
    
def test_perhaps_suppress_instructorinfo():
    md.md.mode = b.Mode.INSTRUCTOR
    content = "one [SECTION::forinstructor::x] two [ENDSECTION] three"
    assert md.SedrilaPreprocessor(md.md).perhaps_suppress_instructorinfo(content) == "one  three"