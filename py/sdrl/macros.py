"""Macros extend Markdown by a [MYMACRO::arg1::arg2] syntax."""

import dataclasses
import re
import typing as tg

import markdown

import base as b

@dataclasses.dataclass
class Macrocall:
    """Represent where and how a macro was called, allow producing errors/warnings for it."""
    md: markdown.Markdown
    filename: str
    macrocall_text: str
    macroname: str
    arg1: b.OStr
    arg2: b.OStr

    def error(self, msg: str):
        b.error(f"'{self.filename}': {self.macrocall_text}\n  {msg}")

    def warning(self, msg: str):
        b.warning(f"'{self.filename}': {self.macrocall_text}\n  {msg}")


Macroexpander = tg.Callable[[Macrocall], str]
Macrodef = tg.Tuple[str, int, Macroexpander]  # name, num_args, expander

macrodefs: dict[str, tg.Tuple[int, Macroexpander]] = dict()


macro_regexp = r"\[([A-Z][A-Z0-9_]+)(?:::(.+?))?(?:::(.+?))?\](?=[^(]|$)"  
# bracketed all-caps: [ALL2_CAPS] with zero to two arguments: [NAME::arg] or [NAME::arg1::arg2]
# suppress matches on normal links: [TEXT](url)


def expand_macros(sourcefile: str, markup: str) -> str:
    """Apply matching macrodefs, report errors for non-matching macro calls."""
    def my_expand_macro(mm: re.Match) -> str:
        return expand_macro(sourcefile, mm)
    return re.sub(macro_regexp, my_expand_macro, markup)


def expand_macro(sourcefile: str, mm: re.Match) -> str:
    """Apply matching macrodef or report error."""
    global macrodefs
    import sdrl.markdown
    call, macroname, arg1, arg2 = mm.group(), mm.group(1), mm.group(2), mm.group(3)
    macrocall = Macrocall(md=sdrl.markdown.md, filename=sourcefile, macrocall_text=call,
                          macroname=macroname, arg1=arg1, arg2=arg2)
    my_numargs = (arg1 is not None) + (arg2 is not None)
    # ----- check name:
    if macroname not in macrodefs:
        macrocall.error(f"Macro '{macroname}' is not defined")
        return call  # unexpanded version helps the user most
    numargs, expander = macrodefs[macroname]
    # ----- check args:
    if my_numargs != numargs:
        macrocall.error("Macro '%s' called with %d args, expects %d" %
                        (macroname, my_numargs, numargs))
        return call  # unexpanded version helps the user most
    # ----- expand:
    b.debug(f"expanding {macrocall.macrocall_text}")
    return expander(macrocall)


def register_macro(name: str, numargs: int, expander: Macroexpander):
    global macrodefs
    assert name not in macrodefs  # TODO_2: turn into checks with nice error messages
    assert 0 <= numargs <= 2
    assert name == name.upper()  # must be all uppercase
    macrodefs[name] = (numargs, expander)
