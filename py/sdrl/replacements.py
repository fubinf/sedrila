"""
Manage the replacements data for the <replacement id='abcde'>...</replacement> markdown extension
It comes from a file that contains as many such <replacement> groups as needed,
separated by whatever, e.g. two empty lines.
"""
import re

import base

replacement_expr_re = r"<replacement +?id=[\'\"]([\w_-]+?)[\'\"]>(.+?)</replacement>"
replacementsdict = dict()
replacements_loaded = False  # nothing has been loaded, so just keep the original content

def load_replacements_file(filename: str):
    with open(filename, 'rt', encoding='utf8') as f:
        load_replacements_string(f.read())


def load_replacements_string(context_filename: str, s: str):
    global replacementsdict, replacements_loaded
    for id, body in re.findall(replacement_expr_re, s, flags=re.DOTALL):
        if id in replacementsdict:
            base.warning(f"'{context_filename}': replacement '{id}' is defined multiple times")
        replacementsdict[id] = body
    replacements_loaded = True


def get_replacement(context_filename: str, content: str, id: str) -> str:
    global replacementsdict, replacements_loaded
    if not replacements_loaded:
        return content
    if id not in replacementsdict:
        base.warning(f"'{context_filename}': replacement '{id}' is not defined, using '????'")
    return replacementsdict.get(id, "????")
