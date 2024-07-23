# pytest tests

import base as b
import sdrl.macros as macros
import sdrl.macroexpanders

def expander(macrocall: macros.Macrocall):
    return f"{macrocall.macroname}({macrocall.arg1},{macrocall.arg2})"


def test_expand_macros():
    b._testmode_reset()
    macros._testmode_reset()
    macros.register_macro('MA', 0, macros.MM.INNER, expander)
    macros.register_macro('MB', 1, macros.MM.INNER, expander)
    macros.register_macro('MC', 2, macros.MM.INNER, expander)
    assert macros.expand_macros("-",  "-", 
                                "a [MA], b [MB::argb], c [MC::c1::c2], d") == "a MA(None,None), b MB(argb,None), c MC(c1,c2), d" 
    

def test_expand_nonexisting_macro(capsys):
    b._testmode_reset()
    macros._testmode_reset()
    macros.register_macro('MA', 0, macros.MM.INNER, expander)
    assert macros.expand_macros("-", "-", "[MABC]") == "[MABC]"
    out, err = capsys.readouterr()
    assert "not defined" in out


def test_expand_macro_with_wrong_args(capsys):
    b._testmode_reset()
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


def test_includefile_path():
    class Course:
        altdir = "altdir/ch"
        itreedir = "altdir/itree.zip"
        chapterdir = "ch"

    # ----- prepare:
    course = Course()  # dummy Course/Coursebuilder object
    b._testmode_reset()
    # ----- perform tests:
    def func(arg: str, itree_mode=False) -> str:
        call = macros.Macrocall(None, "ch/chapter/group/task.md", "task",
                                f"[INCLUDE::{arg}]", "INCLUDE", arg, None)
        return sdrl.macroexpanders.includefile_path(course, call, itree_mode)

    assert func("other") == "ch/chapter/group/other"
    assert func("/other2") == "ch/other2"
    assert func("ALT:other") == "altdir/ch/chapter/group/other"
    assert func("ALT:/other2") == "altdir/ch/other2"
    assert func("ALT:") == "altdir/ch/chapter/group/task.md"
    assert func("other", itree_mode=True) == "altdir/itree.zip/chapter/group/other"
    assert func("/other2", itree_mode=True) == "altdir/itree.zip/other2"


