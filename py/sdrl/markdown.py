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
        content = macros.expand_macros(self.md.context_sourcefile, self.md.partname, content,
                                       is_early_phase=True)
        # content = SedrilaPostprocessor.hide_html_tags(content)
        return content.split("\n")

    def perhaps_suppress_instructorinfo(self, content: str) -> str:
        """in instructor mode, suppress all [INSTRUCTOR::heading] texttexttext [ENDINSTRUCTOR] blocks"""
        if self.md.mode == b.Mode.INSTRUCTOR:
            return content  # leave instructorinfo in instructor mode
        else:               # remove instructorinfo in student mode
            block_re = r"\[INSTRUCTOR::.+?ENDINSTRUCTOR\]"  # non-greedy middle part, just in case
            newcontent = re.sub(block_re, "", content, flags=re.DOTALL)
            return newcontent

    def make_replacements(self, content: str) -> str:
        def the_repl(mm: re.Match) -> str:
            return replacements.get_replacement(self.md.context_sourcefile, mm.group(2), mm.group(1))            
        return re.sub(replacements.replacement_expr_re, the_repl, content, flags=re.DOTALL)


class SedrilaPostprocessor(mdpost.Postprocessor):
    LT_ERSATZ = "\u269f"  # ⚟ 
    GT_ERSATZ = "\u269e"  # ⚞ 
    AMP_ERSATZ = "\u203b"  # ※ 
    RE_GROUP1 = r"\1"
    lt_hide_search_re = r"<(\S)"
    gt_hide_search_re = r"(\S)>"
    htmlesc_hide_search_re = r"&(\S)"
    lt_hide_repl_re = LT_ERSATZ + RE_GROUP1
    gt_hide_repl_re = RE_GROUP1 + GT_ERSATZ
    htmlesc_hide_repl_re = AMP_ERSATZ + RE_GROUP1
    lt_unhide_search_re = f"(<p>)?" + LT_ERSATZ
    gt_unhide_search_re = GT_ERSATZ + f"(</p>)?"
    amp_unhide_search_str = AMP_ERSATZ
    lt_unhide_repl_re = "<"
    gt_unhide_repl_re = ">"
    amp_unhide_repl_str = "&"

    def run(self, text: str) -> str:
        text = macros.expand_macros(self.md.context_sourcefile, self.md.partname, text)
        return text
        # return self.unhide_html_tags(text)  # hide_html_tags() happens in the preprocessor

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
        BEWARE: 
        - There will be '<' and '>' in normal Markdown text as well.
          These do not represent HTML tags and must be kept, 
          so that Markdown can encode them as '&lt;' and '&gt;' later.
        - To show HTML source text in our Markdown files, that HTML will have to be sent
          through an escaping filter (that encodes "<p>" as "&lt;p&gt;" etc.).
          Therefore, we must protect HTML escape sequences by replacing their '&' and
          undoing that later.
        - Of course, '&' characters that are not part of an HTML escape sequence
          must be left alone, so that Markdown can convert them into '&amp;'.
        - And of course, you must never use those obscure replacement characters in your
          Markdown text yourself.
        (If your head is now spinning, that's not you, it's a domain property.) 
        """
        content = re.sub(cls.lt_hide_search_re, cls.lt_hide_repl_re, content)
        content = re.sub(cls.gt_hide_search_re, cls.gt_hide_repl_re, content)
        content = re.sub(cls.htmlesc_hide_search_re, cls.htmlesc_hide_repl_re, content)
        return content
    
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
        content = re.sub(cls.lt_unhide_search_re, cls.lt_unhide_repl_re, content)
        content = re.sub(cls.gt_unhide_search_re, cls.gt_unhide_repl_re, content)
        content = content.replace(cls.amp_unhide_search_str, cls.amp_unhide_repl_str)
        return content


class AdmonitionFilter(mdt.Treeprocessor):
    def run(self, root):
        """Removes admonition div blocks not to be shown in current self.mode."""
        for divparent in root.findall('.//div/..'):  # sadly, etree does not support contains()
            for div in divparent.findall('div'):
                classes = div.attrib.get('class', '')
                if 'admonition' in classes and 'instructor' in classes and self.md.mode != b.Mode.INSTRUCTOR:
                    divparent.remove(div)  # show  !!! instructor  blocks only in instructor mode


def render_markdown(context_sourcefile: str, partname: str, markdown_markup: str, 
                    mode: b.Mode, blockmacro_topmatter: dict[str, str]) -> str:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    # hand config data into the Markdown object as undeclared attributes:
    md.mode = mode
    md.context_sourcefile = context_sourcefile
    md.partname = partname
    md.blockmacro_topmatter = blockmacro_topmatter
    return md.reset().convert(markdown_markup)


# ######### initialization:

extensions = [SedrilaExtension(), 
              'admonition', 'attr_list', 'codehilite', 'fenced_code',
              'sane_lists', 'toc', 'smarty',
             ]
# https://python-markdown.github.io/extensions/admonition/
# https://python-markdown.github.io/extensions/attr_list/
# https://python-markdown.github.io/extensions/code_hilite/
# https://python-markdown.github.io/extensions/fenced_code_blocks/
# https://python-markdown.github.io/extensions/sane_lists/
# https://python-markdown.github.io/extensions/smarty/
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

md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
# '[TOC]' is Markdown, but looks syntactically like a macro call, so make 'TOC' a macro:
macros.register_macro('TOC', 0, macros.MM.EARLY, lambda mc: f"[{mc.macroname}]")
