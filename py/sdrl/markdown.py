"""Markdown rendering with sedrila-specific bells and/or whistles."""
import dataclasses
import re
import typing as tg
import markdown
import markdown.extensions as mde
import markdown.preprocessors as mdp
import markdown.treeprocessors as mdt

import base as b

# see bottom for initialization code


@dataclasses.dataclass
class Macrocall:
    """Represent where and how a macro was called, allow producing errors/warnings for it."""
    filename: str
    macrocall_text: str

    def error(self, msg: str):
        b.error(f"'{self.filename}': {self.macrocall_text}\n  {msg}")

    def warning(self, msg: str):
        b.warning(f"'{self.filename}': {self.macrocall_text}\n  {msg}")


Macroexpander = tg.Callable[[Macrocall, str, b.OStr, b.OStr], str]
Macrodef = tg.Tuple[str, int, Macroexpander]  # name, num_args, expander

macrodefs: dict[str, tg.Tuple[int, Macroexpander]] = dict()


macro_regexp = r"\[([A-Z][A-Z0-9_]+)(?:::(.+?))?(?:::(.+?))?\](?=[^(]|$)"  
# bracketed all-caps: [ALL2_CAPS] with zero to two arguments: [NAME::arg] or [NAME::arg1::arg2]
# suppress matches on normal links: [TEXT](url)


class SedrilaExtension(mde.Extension):
    def extendMarkdown(self, md):
        # Register instance of 'mypattern' with a priority of 175
        md.preprocessors.register(SedrilaPreprocessor(md), 'sedrila_preprocessor', 50)
        md.preprocessors.deregister('html_block')  # do not treat the markdown blocks as fixed HTML
        md.treeprocessors.register(AdmonitionFilter(md), "admonition_filter", 100)


class SedrilaPreprocessor(mdp.Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        content = "\n".join(lines)  # we work on the entire markup at once
        content2 = self.perhaps_suppress_instructorinfo(content)  
        content3 = expand_macros(self.md.context_sourcefile, content2)
        return content3.split("\n")

    def perhaps_suppress_instructorinfo(self, content: str) -> str:
        """in instructor mode, suppress all [SECTION::forinstructor::x] texttexttext [ENDSECTION] blocks"""
        if self.md.mode == b.Mode.INSTRUCTOR:
            return content  # leave instructorinfo in instructor mode
        else:               # remove instructorinfo in student mode
            block_re = r"\[SECTION::forinstructor.+?ENDSECTION\]"  # non-greedy middle part!
            newcontent = re.sub(block_re, "", content, flags=re.DOTALL)
            return newcontent


def expand_macros(sourcefile: str, markup: str) -> str:
    """Apply matching macrodefs, report errors for non-matching macro calls."""
    def my_expand_macro(mm: re.Match) -> str:
        return expand_macro(sourcefile, mm)
    return re.sub(macro_regexp, my_expand_macro, markup)


def expand_macro(sourcefile: str, mm: re.Match) -> str:
    """Apply matching macrodef or report error."""
    global macrodefs
    call, macroname, arg1, arg2 = mm.group(), mm.group(1), mm.group(2), mm.group(3)
    macrocall = Macrocall(filename=sourcefile, macrocall_text=call)
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
    return expander(macrocall, macroname, arg1, arg2)


def register_macro(name: str, numargs: int, expander: Macroexpander):
    global macrodefs
    assert name not in macrodefs  # TODO_2: turn into checks with nice error messages
    assert 0 <= numargs <= 2
    assert name == name.upper()  # must be all uppercase
    macrodefs[name] = (numargs, expander)


class AdmonitionFilter(mdt.Treeprocessor):
    def run(self, root):
        """Removes admonition div blocks not to be shown in current self.mode."""
        for divparent in root.findall('.//div/..'):  # sadly, etree does not support contains()
            for div in divparent.findall('div'):
                classes = div.attrib.get('class', '')
                if 'admonition' in classes and 'instructor' in classes and self.md.mode != b.Mode.INSTRUCTOR:
                    divparent.remove(div)  # show  !!! instructor  blocks only in instructor mode


def render_markdown(context_sourcefile: str, markdown_markup: str, mode: b.Mode) -> str:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    md.mode = mode
    md.context_sourcefile = context_sourcefile
    return md.reset().convert(markdown_markup)


# ######### initialization:

extensions = [SedrilaExtension(), 
              'admonition', 'attr_list', 'fenced_code', 'toc', 'codehilite']
# https://python-markdown.github.io/extensions/admonition/
# https://python-markdown.github.io/extensions/attr_list/
# https://python-markdown.github.io/extensions/fenced_code_blocks/
# https://python-markdown.github.io/extensions/toc/
# https://python-markdown.github.io/extensions/code_hilite/

extension_configs = {
    'toc': {
        # 'slugify':  perhaps replace with numbering-aware version 
    }
}

md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
# '[TOC]' is a macro call, so make 'TOC' a macro:
register_macro('TOC', 0, lambda mc, m, a1, a2: f"[{m}]")
