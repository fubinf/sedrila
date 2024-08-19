"""
Macros extend Markdown by a [MYMACRO::arg1::arg2] syntax.
A macro expands into text and may have state.

# Architecture

## 4 macro modes

Any macro belongs to one of the following modes of working:
- EARLY: The macro produces Markdown markup and will be expanded in the preprocessor stage of 
  the Markdown module. 
  Macros of the other modes all get expanded in the postprocessor stage.
- INNER: The macro produces a fragment of HTML text within a paragraph.
- BLOCK: The macro produces a self-contained <div>...</div> block.
- BLOCKSTART: The macro produces (among other things) an HTML opening tag.
- BLOCKEND: The macro produces (possibly among other things) the corresponding closing tag.

## The <p>-problem

The most basic mechanism of Markdown is recognizing blocks of text between empty lines
as paragraphs and enclose the text in <p>...</p> tags.
This is problematic for blockstart and blockend macros, because having their opening
tag (say, <div>) between <p> and </p> creates malformed HTML.
We call this the <p>-problem.

## Solution of the <p>-problem

Let us assume [START] is a blockstart macro and [END] is a blockend macro.
In terms of its line layout, the structure of the switch from one block to the next
may look like this:

Layout 1        2           3           4

text          text        text        text
[END]         [END]
[START]                   [END]       [END]
text          [START]     [START]
              text                    [START]
                          text
                                      text

Layout 1 will become enclosed in a single <p>...</p> pair and cannot be repaired easily.
It must not be used.

Layout 2 will involve "[END]</p>" and "<p>[START]", 
which will be turned into "</p>[END]" and "[START]<p>".

Layout 3 will involve "<p>[END]\n[START]</p>", 
which will be turned into "[END]\n[START]".

Layout 4 will involve "<p>[END]</p>" and "<p>[START]</p>", 
which will be turned into "[END]" and "[START]".

This way, the tag structures created by (properly used) block macros stay intact
and the text is still properly surrounded by <p>...</p>

## Macro state

The module has a single state object called macrostate,
which is a dictionary with one slot per macro: the macro name.
Macros have a 'switcher' callback function that gets called whenever processing
of a course part starts. This can reset state if needed.

"""

import dataclasses
import enum
import itertools
import re
import typing as tg

import base as b


@dataclasses.dataclass
class Macrocall:
    """Represent where and how a macro was called, allow producing errors/warnings for it."""
    md: 'SedrilaMarkdown'  # noqa
    filename: str
    partname: str
    macrocall_text: str
    macroname: str
    arg1: b.OStr
    arg2: b.OStr

    def error(self, msg: str):
        b.error(f"{self.macrocall_text}\n   {msg}", file=self.filename)

    def warning(self, msg: str):
        b.warning(f"{self.macrocall_text}\n   {msg}", file=self.filename)


class MM(enum.Enum):
    """MacroMode"""
    EARLY = 1
    INNER = 2
    BLOCK = 3
    BLOCKSTART = 4
    BLOCKEND = 5


Macroexpander = tg.Callable[[Macrocall], str]
Partswitcher = tg.Callable[[str, str], None]  # macroname, newpartname
Macrodef = tg.Tuple[int, MM, Macroexpander, Partswitcher]  # num_args, expander, switcher

macrodefs_early: dict[str, Macrodef] = dict()  # macroname -> macrodef
macrodefs_late: dict[str, Macrodef] = dict()  # macroname -> macrodef
macrostate: dict[str, tg.Any] = dict()  # namespace -> state_object

macro_regexp = (r"(?P<ppre></?p>)?"
                r"(?P<macrocall>\[(?P<name>[A-Z][A-Z0-9_]+)(::(?P<arg1>.*?))?(::(?P<arg2>.*?))?\])"
                r"(?=[^(]|$)(?P<ppost></?p>)?")  
# bracketed all-caps: [ALL2_CAPS] with zero to two arguments: [NAME::arg] or [NAME::arg1::arg2]
# suppress matches on normal links: [TEXT](url)


def expand_macros(sourcefile: str, partname: str, markup: str, is_early_phase=False) -> str:
    """Apply matching macrodefs, report errors for non-matching macro calls."""
    def my_expand_macro(mm: re.Match) -> str:
        return expand_macro(sourcefile, partname, mm, is_early_phase)
    return re.sub(macro_regexp, my_expand_macro, markup)


def expand_macro(sourcefile: str, partname: str, mm: re.Match, is_early_phase=False) -> str:
    """Apply matching macrodef or report error or wait for late phase to report it then."""
    global macrodefs_early, macrodefs_late
    import sdrl.markdown
    macrodefs = (macrodefs_early if is_early_phase else macrodefs_late)
    ppre, call, ppost = mm.group('ppre'), mm.group('macrocall'), mm.group('ppost')
    macroname, arg1, arg2 = mm.group('name'), mm.group('arg1'), mm.group('arg2')
    macrocall = Macrocall(md=sdrl.markdown.md, filename=sourcefile, partname=partname,
                          macrocall_text=call,
                          macroname=macroname, arg1=arg1, arg2=arg2)
    my_numargs = (arg1 is not None) + (arg2 is not None)
    # ----- check name:
    if macroname not in macrodefs:
        if not is_early_phase:  # so we do not complain twice
            macrocall.error(f"Macro '{macroname}' is not defined")
        return call  # unexpanded version helps the user most
    numargs, mode, expander, switcher = macrodefs[macroname]
    # ----- check args:
    if my_numargs != numargs:
        if not is_early_phase:  # so we do not complain twice
            macrocall.error("Macro '%s' called with %d args, expects %d" %
                            (macroname, my_numargs, numargs))
        return call  # unexpanded version helps the user most
    if my_numargs > 0 and arg1 == "":
        macrocall.warning("Macro '%s' called with empty argument 1" % macroname)
    # ----- expand:
    # b.debug(f"expanding {macrocall.macrocall_text}")
    expansion = expander(macrocall)
    # ----- handle ppre and ppost:
    ppre = ppre if ppre else ""  # fill in "" for None
    ppost = ppost if ppost else ""
    if mode == MM.EARLY:
        pass  # use ppre, ppost verbatim
    elif mode == MM.INNER:
        pass  # ditto
    elif mode == MM.BLOCK:
        pass  # ditto
    elif mode == MM.BLOCKSTART:
        if not ppre and not ppost:  # Layout 1
            macrocall.warning("blockmacro blocks must be separated by empty lines _somewhere_")
        elif ppre == '<p>' and not ppost:  # Layout 2
            ppost = ppre  # shift <p> from front to back
            ppre = ""
        elif not ppre and ppost == '</p>':  # Layout 3
            ppost = ""  # remove
        elif ppre == '<p>' and ppost == '</p>':  # Layout 4
            ppre = ""  # remove
            ppost = ""  # remove
        else:
            assert False
    elif mode == MM.BLOCKEND:
        if not ppre and not ppost:  # Layout 1
            pass  # warn at BLOCKSTART
        elif not ppre and ppost == '</p>':  # Layout 2
            ppre = ppost  # shift </p> from back to front
            ppost = ""
        elif ppre == '<p>' and not ppost:  # Layout 3
            ppre = ""  # remove
        elif ppre == '<p>' and ppost == '</p>':  # Layout 4
            ppre = ""  # remove
            ppost = ""  # remove
        else:
            assert False, mm.group()
    else:
        assert False    
    # return f"pre<{ppre}>exp<{expansion}>post<{ppost}>"
    result = f"{ppre}{expansion}{ppost}"
    return result


def get_state(namespace: str) -> tg.Any:
    return macrostate[namespace]  # must exist


def set_state(namespace: str, obj: tg.Any):
    global macrostate
    macrostate[namespace] = obj


def switch_part(newpartname: str):
    """Patch all macrodefs to mention a different part than previously (yes, it's ugly)."""
    for macroname, macrodef in itertools.chain(macrodefs_early.items(), macrodefs_late.items()):
        nargs, mode, expander, switcher = macrodef
        switcher(macroname, newpartname)


def register_macro(name: str, numargs: int, mode: MM, expander: Macroexpander, 
                   switcher: Partswitcher = lambda mn, pn: None, 
                   redefine=False):
    global macrodefs_early, macrodefs_late
    macrodefs = (macrodefs_early if mode == MM.EARLY else macrodefs_late)
    if redefine:
        assert name in macrodefs
    else:
        assert name not in macrodefs
    assert 0 <= numargs <= 2
    assert name == name.upper()  # macronames must be all uppercase
    macrodefs[name] = (numargs, mode, expander, switcher)


def _testmode_reset():
    global macrodefs_early, macrodefs_late, macrostate
    macrodefs_early, macrodefs_late = (dict(), dict())
    macrostate = dict()