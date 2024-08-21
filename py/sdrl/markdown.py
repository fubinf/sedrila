"""
Markdown rendering with sedrila-specific bells and/or whistles.
"""
import re

import markdown
import markdown.extensions as mde
import markdown.preprocessors as mdpre
import markdown.postprocessors as mdpost

import base as b
import sdrl.macros as macros
import sdrl.replacements as replacements

# see bottom for initialization code


class SedrilaExtension(mde.Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(SedrilaPreprocessor(md), 'sedrila_preprocessor', 50)
        md.postprocessors.register(SedrilaPostprocessor(md), 'sedrila_postprocessor', 10)


class SedrilaPreprocessor(mdpre.Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        content = "\n".join(lines)  # we work on the entire markup at once
        content = self.perhaps_suppress_instructorinfo(content)  
        content = self.make_replacements(content)
        content = macros.expand_macros(self.md.context_sourcefile, self.md.partname, content,
                                       is_early_phase=True)
        return content.split("\n")

    def perhaps_suppress_instructorinfo(self, content: str) -> str:
        """in instructor mode, suppress all [INSTRUCTOR::heading] texttexttext [ENDINSTRUCTOR] blocks"""
        if self.md.mode == b.Mode.INSTRUCTOR:
            return content  # leave instructorinfo in instructor mode
        else:               # remove instructorinfo in student mode
            block_re = r"\[INSTRUCTOR::.+?ENDINSTRUCTOR\]"  # non-greedy middle part, just in case
            newcontent = re.sub(block_re, "", content, flags=re.DOTALL)
            nonblock_re = r"\[INSTRUCTOR::.+\]"  # find incomplete blocks that were not removed
            mm = re.search(nonblock_re, newcontent)
            if mm:
                b.error(f"call '{mm.group(0)}' lacks [ENDINSTRUCTOR]", file=md.context_sourcefile)
            return newcontent

    def make_replacements(self, content: str) -> str:
        def the_repl(mm: re.Match) -> str:
            return replacements.get_replacement(self.md.context_sourcefile, mm.group(2), mm.group(1))            
        return re.sub(replacements.replacement_expr_re, the_repl, content, flags=re.DOTALL)


class SedrilaPostprocessor(mdpost.Postprocessor):
    def run(self, text: str) -> str:
        text = macros.expand_macros(self.md.context_sourcefile, self.md.partname, text)
        return text


class SedrilaMarkdown(markdown.Markdown):
    mode: macros.MM
    context_sourcefile: str
    partname: str
    blockmacro_topmatter: dict[str, str]
    includefiles: set[str]  # [INCLUDE::...], [PROT::...] will add a filename here
    termrefs: set[str]  # [TERMREF::...] will add a term alias here


def render_markdown(context_sourcefile: str, partname: str, markdown_markup: str, 
                    mode: b.Mode, blockmacro_topmatter: dict[str, str]) -> b.StrAnyDict:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    md.mode = mode
    md.context_sourcefile = context_sourcefile
    md.partname = partname
    md.blockmacro_topmatter = blockmacro_topmatter
    md.includefiles = set()
    md.termrefs = set()
    html = md.reset().convert(markdown_markup)
    return dict(html=html, includefiles=md.includefiles, termrefs=md.termrefs)

# ######### initialization:

extensions = [SedrilaExtension(), 
              'attr_list', 'codehilite', 'fenced_code',
              'sane_lists', 'tables', 'toc', 'smarty',
              ]
# https://python-markdown.github.io/extensions/attr_list/
# https://python-markdown.github.io/extensions/code_hilite/
# https://python-markdown.github.io/extensions/fenced_code_blocks/
# https://python-markdown.github.io/extensions/sane_lists/
# https://python-markdown.github.io/extensions/smarty/
# https://python-markdown.github.io/extensions/tables/
# https://python-markdown.github.io/extensions/toc/
# https://github.com/daGrevis/mdx_linkify  breaks the correct handling of `a < b` and cannot be used

extension_configs = {
    'toc': {
        # 'slugify':  perhaps replace with numbering-aware version 
    },
    'codehilite': {
        'linenums': True
    },
    'smarty': {
        'smart_quotes': False
    }
}

md = SedrilaMarkdown(extensions=extensions, extension_configs=extension_configs)
# '[TOC]' is Markdown, but looks syntactically like a macro call, so make 'TOC' a macro:
macros.register_macro('TOC', 0, macros.MM.INNER, lambda mc: f"[{mc.macroname}]")
