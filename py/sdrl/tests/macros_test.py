# pytest tests

import base as b
import sdrl.macros as macros

def expander(macrocall: macros.Macrocall):
    return f"{macrocall.macroname}({macrocall.arg1},{macrocall.arg2})"


def test_expand_macros():
    macros._testmode_reset()
    macros.register_macro('MA', 0, macros.MM.INNER, expander)
    macros.register_macro('MB', 1, macros.MM.INNER, expander)
    macros.register_macro('MC', 2, macros.MM.INNER, expander)
    assert macros.expand_macros("-",  "-", 
                                "a [MA], b [MB::argb], c [MC::c1::c2], d") == "a MA(None,None), b MB(argb,None), c MC(c1,c2), d" 
    

def test_expand_nonexisting_macro(capsys):
    macros._testmode_reset()
    macros.register_macro('MA', 0, macros.MM.INNER, expander)
    assert macros.expand_macros("-", "-", "[MABC]") == "[MABC]"
    out, err = capsys.readouterr()
    assert "not defined" in out


def test_expand_macro_with_wrong_args(capsys):
    macros._testmode_reset()
    macros.register_macro('MA', 0, macros.MM.INNER, expander)
    macros.register_macro('MB', 1, macros.MM.INNER, expander)
    macros.register_macro('MC', 2, macros.MM.INNER, expander)
    assert macros.expand_macros("(nofile)", "nopart", 
                                "[MA::onearg][MB::two::args][MC]") == "[MA::onearg][MB::two::args][MC]"
    log_out, err = capsys.readouterr()
    assert "'(nofile)'" in log_out 
    assert "[MA::onearg]" in log_out 
    assert "expects 0" in log_out 
    assert "expects 1" in log_out
    assert "expects 2" in log_out
