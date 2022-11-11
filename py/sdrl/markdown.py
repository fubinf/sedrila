"""Markdown rendering with sedrila-specific bells and/or whistles."""
import re
import typing as tg

import markdown

import sdrl.html as h

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

abbreviations = [  # all-uppercase literal replacements done before Markdown rendering
    ('[DIFF1]', h.difficulty_symbol(1)),
    ('[DIFF2]', h.difficulty_symbol(2)),
    ('[DIFF3]', h.difficulty_symbol(3)),
    ('[DIFF4]', h.difficulty_symbol(4)),
]

abbreviation_regexp = r"\[[A-Z0-9_]\]"  # bracketed all-caps stuff: [ALL2_CAPS]


def render_markdown(markdown_markup: str) -> str:
    """
    Generates HTML from Markdown in sedrila manner.
    See https://python-markdown.github.io/
    """
    return markdown.markdown(replace_abbreviations(markdown_markup, *abbreviations), 
                             extensions=extensions, extension_configs=extension_configs)


def replace_abbreviations(markup: str, *pairs: tg.Sequence[tg.Tuple[str, str]]) -> str:
    # if not re.search(abbreviation_regexp, markup):
    #     return markup  # nothing replaceable seen
    for abbrev, replacement in pairs:  # inefficient, but probably not a problem
        markup = markup.replace(abbrev, replacement)
    return markup