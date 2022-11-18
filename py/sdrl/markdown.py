"""Markdown rendering with sedrila-specific bells and/or whistles."""
import re
import typing as tg

import markdown

import base as b
import sdrl.html as h

Macroexpander = tg.Callable[[str, str, str], str]
Macrodef = tg.Union[tg.Tuple[str, int], tg.Tuple[str, int, Macroexpander]]  # name, num_args, expander

macrodefs: tg.Mapping[str, tg.Tuple[int, Macroexpander]] = dict()

extensions = ['attr_list', 'fenced_code', 'toc']
# https://python-markdown.github.io/extensions/attr_list/
# https://python-markdown.github.io/extensions/fenced_code_blocks/
# https://python-markdown.github.io/extensions/toc/
# Also consider
# https://python-markdown.github.io/extensions/code_hilite/  code with syntax highlighting

extension_configs = {
    'toc': {
        # 'slugify':  perhaps replace with numbering-aware version 
    }
}

macro_regexp = r"\[([A-Z0-9_]+)(?:::(.+?))?(?:::(.+?))?\]"  
# bracketed all-caps: [ALL2_CAPS] with zero to two arguments: [NAME::arg] or [NAME::arg1::arg2]


def expand_macros(markup: str) -> str:
    """Apply matching macrodefs, report errors for non-matching macro calls."""
    return re.sub(macro_regexp, expand_macro, markup)


def expand_macro(mm: re.Match) -> str:
    """Apply matching macrodef or report error."""
    global macrodefs
    call, macroname, arg1, arg2 = mm.group(), mm.group(1), mm.group(2), mm.group(3)
    my_numargs = (arg1 is not None) + (arg2 is not None)
    #----- check name:
    if macroname not in macrodefs:
        b.error(f"Macro '{macroname}' is not defined: {call}")
        return call  # unexpanded version helps the user most
    numargs, expander = macrodefs[macroname]
    #----- check args:
    if my_numargs != numargs:
        b.error("Macro '%s' called with %d args, expects %d:  %s" %
                (macroname, my_numargs, numargs, call))
        return call  # unexpanded version helps the user most
    #----- expand:
    return expander(macroname, arg1, arg2)


def register_macro(name: str, numargs: int, expander: Macroexpander):
    global macrodefs
    assert name not in macrodefs
    assert 0 <= numargs <= 2
    assert name == name.upper()  # must be all uppercase
    macrodefs[name] = (numargs, expander)


def register_macros(*, macros: tg.Sequence[Macrodef], expander: tg.Optional[Macroexpander] = None):
    global macrodefs
    for macrodef in macros:
        if len(macrodef) == 2:
            name, numargs = macrodef
            register_macro(name, numargs, expander)
        else:
            assert len(macrodef) == 3
            register_macro(*macrodef)

def render_markdown(markdown_markup: str) -> str:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    return markdown.markdown(expand_macros(markdown_markup), 
                             extensions=extensions, 
                             extension_configs=extension_configs)
