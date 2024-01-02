"""
Markdown rendering with sedrila-specific bells and/or whistles.

The current design of the solution (based on preprocessor+postprocessor) is ugly.
A better approach would be using (at least for the macros part) a block processor
combined with https://python-markdown.github.io/extensions/md_in_html/.
But the current one works and is Good Enough.
"""
import re

import markdown
import markdown.extensions as mde
import markdown.preprocessors as mdpre
import markdown.postprocessors as mdpost
import markdown.treeprocessors as mdt

import base as b
import sdrl.macros as macros
import sdrl.replacements as replacements

# see bottom for initialization code


class SedrilaExtension(mde.Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(SedrilaPreprocessor(md), 'sedrila_preprocessor', 50)
        # md.preprocessors.deregister('html_block')  # do not treat the markdown blocks as fixed HTML
        md.treeprocessors.register(AdmonitionFilter(md), "admonition_filter", 100)
        md.postprocessors.register(SedrilaPostprocessor(md), 'sedrila_postprocessor', 10)


class SedrilaPreprocessor(mdpre.Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        content = "\n".join(lines)  # we work on the entire markup at once
        content = self.perhaps_suppress_instructorinfo(content)  
        content = self.make_replacements(content)  
        content = macros.expand_macros(self.md.context_sourcefile, content)
        content = SedrilaPostprocessor.hide_html_tags(content)
        return content.split("\n")

    def perhaps_suppress_instructorinfo(self, content: str) -> str:
        """in instructor mode, suppress all [SECTION::forinstructor::x] texttexttext [ENDSECTION] blocks"""
        if self.md.mode == b.Mode.INSTRUCTOR:
            return content  # leave instructorinfo in instructor mode
        else:               # remove instructorinfo in student mode
            block_re = r"\[SECTION::forinstructor.+?ENDSECTION\]"  # non-greedy middle part!
            newcontent = re.sub(block_re, "", content, flags=re.DOTALL)
            return newcontent

    def make_replacements(self, content: str) -> str:
        def the_repl(mm: re.Match) -> str:
            return replacements.get_replacement(self.md.context_sourcefile, mm.group(2), mm.group(1))            
        return re.sub(replacements.replacement_expr_re, the_repl, content, flags=re.DOTALL)


class SedrilaPostprocessor(mdpost.Postprocessor):
    LT_ERSATZ = "\u269f"  # ⚟ 
    GT_ERSATZ = "\u269e"  # ⚞ 

    def run(self, text: str) -> str:
        return self.unhide_html_tags(text)  # hide_html_tags() happens in the preprocessor

    @classmethod
    def hide_html_tags(cls, content: str) -> str:
        """
        This method is called from the Preprocessor!
        Our macros create long-ranging HTML tag pairs that contain Markdown markup as text.
        This is nothing that Python-Markdown was made for: 
        It will by default stash away the entire block and not process its Markdown markup.
        If we deactivate the html_block preprocessor that performs the stashing,
        the HTML tags end up wrapped (even wrongly) in <p> </p> pairs.
        So we hide the HTML tags by 
        replacing '<' and '>' by obscure Unicode characters in a preprocessor
        and undoing this in the present postprocessor at the end.
        """
        return content.replace('<', cls.LT_ERSATZ).replace('>', cls.GT_ERSATZ)
    
    @classmethod
    def unhide_html_tags(cls, content: str) -> str:
        """
        See hide_html_tags() for the basic idea.
        But life is even worse than described there:
        Such an escaped tag will either be part of a paragraph or be a standalone paragraph.
        In both cases, there will be a <p> ... </p> pair somewhere around our tag,
        breaking the well-formedness of the HTML.
        The first case can be avoided by having newlines around the generated html code.
        The second case cannot be avoided; it must be repaired:
        We remove <p> right before an LT_ERSATZ and </p> right after a GT_ERSATZ. 
        """
        lt_ersatz_re = f"(<p>)?" + cls.LT_ERSATZ
        gt_ersatz_re = cls.GT_ERSATZ + f"(</p>)?"
        content = re.sub(lt_ersatz_re, '<', content)
        content = re.sub(gt_ersatz_re, '>', content)
        return content


class AdmonitionFilter(mdt.Treeprocessor):
    def run(self, root):
        """Removes admonition div blocks not to be shown in current self.mode."""
        for divparent in root.findall('.//div/..'):  # sadly, etree does not support contains()
            for div in divparent.findall('div'):
                classes = div.attrib.get('class', '')
                if 'admonition' in classes and 'instructor' in classes and self.md.mode != b.Mode.INSTRUCTOR:
                    divparent.remove(div)  # show  !!! instructor  blocks only in instructor mode


def render_markdown(context_sourcefile: str, markdown_markup: str, 
                    mode: b.Mode, blockmacro_topmatter: dict[str, str]) -> str:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    # hand config data into the Markdown object as undeclared attributes:
    md.mode = mode
    md.context_sourcefile = context_sourcefile
    md.blockmacro_topmatter = blockmacro_topmatter
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
    },
    'codehilite': {
        'linenums': True
    }
}

md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
# '[TOC]' is a macro call, so make 'TOC' a macro:
macros.register_macro('TOC', 0, lambda mc: f"[{mc.macroname}]")
