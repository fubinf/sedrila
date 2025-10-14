"""
Markdown rendering with sedrila-specific bells and/or whistles.
"""
import os
import re

import markdown
import markdown.extensions as mde
import markdown.preprocessors as mdpre
import markdown.postprocessors as mdpost

import base as b
import sdrl.macros as macros
import sdrl.replacements as replacements
import sdrl.snippetchecker as snippetchecker

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
        content = self.expand_snippet_inclusions(content)
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
    
    def expand_snippet_inclusions(self, content: str) -> str:
        """Expand @INCLUDE_SNIPPET directives by inserting snippet content from other files."""
        context_file = self.md.context_sourcefile
        
        b.debug(f"expand_snippet_inclusions called for: {context_file}")
        
        # For sedrila, context_file is often a relative path like "ch/Web/Django/django-project.md"
        # We need to find the project root (the directory we're running from)
        
        if os.path.isabs(context_file):
            # Absolute path - extract project root
            if '/ch/' in context_file:
                basedir = context_file.split('/ch/')[0]
            elif '/altdir/' in context_file:
                basedir = context_file.split('/altdir/')[0]
            else:
                # Go up until we find altdir
                basedir = os.path.dirname(context_file)
                while basedir and basedir != '/':
                    if os.path.exists(os.path.join(basedir, 'altdir')):
                        break
                    basedir = os.path.dirname(basedir)
        else:
            # Relative path - use current working directory as project root
            basedir = os.getcwd()
            
            # Verify this is correct by checking if altdir exists
            if not os.path.exists(os.path.join(basedir, 'altdir')):
                # Try to find the correct base directory
                test_dir = basedir
                while test_dir and test_dir != '/':
                    if os.path.exists(os.path.join(test_dir, 'altdir')):
                        basedir = test_dir
                        break
                    test_dir = os.path.dirname(test_dir)
        
        b.debug(f"Derived basedir: {basedir}")
        
        # Check if content contains @INCLUDE_SNIPPET before processing
        if '@INCLUDE_SNIPPET' in content:
            b.debug("Found @INCLUDE_SNIPPET in content, processing...")
        else:
            b.debug("No @INCLUDE_SNIPPET found in content")
        
        result = snippetchecker.expand_snippet_inclusion(content, context_file, basedir)
        
        if result != content:
            b.debug("Content was modified by snippet expansion")
        else:
            b.debug("Content unchanged after snippet expansion")
        
        return result


class SedrilaPostprocessor(mdpost.Postprocessor):
    def run(self, text: str) -> str:
        # Also process snippets in postprocessor stage to catch any missed cases
        if '@INCLUDE_SNIPPET' in text:
            b.debug("Found @INCLUDE_SNIPPET in postprocessor, re-processing...")
            text = self.expand_snippet_inclusions_post(text)
        
        text = macros.expand_macros(self.md.context_sourcefile, self.md.partname, text)
        return text
    
    def expand_snippet_inclusions_post(self, text: str) -> str:
        """Fallback snippet processing in postprocessor stage."""
        context_file = self.md.context_sourcefile
        
        if os.path.isabs(context_file):
            if '/ch/' in context_file:
                basedir = context_file.split('/ch/')[0]
            elif '/altdir/' in context_file:
                basedir = context_file.split('/altdir/')[0]
            else:
                basedir = os.path.dirname(context_file)
                while basedir and basedir != '/':
                    if os.path.exists(os.path.join(basedir, 'altdir')):
                        break
                    basedir = os.path.dirname(basedir)
        else:
            basedir = os.getcwd()
            if not os.path.exists(os.path.join(basedir, 'altdir')):
                test_dir = basedir
                while test_dir and test_dir != '/':
                    if os.path.exists(os.path.join(test_dir, 'altdir')):
                        basedir = test_dir
                        break
                    test_dir = os.path.dirname(test_dir)
        
        return snippetchecker.expand_snippet_inclusion(text, context_file, basedir)


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
