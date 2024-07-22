"""
Manage the replacements data for the <replacement id='abcde'>...</replacement> markdown extension
It comes from a file that contains as many such <replacement> groups as needed,
separated by whatever, e.g. two empty lines.
"""
import re

import base as b

replacement_expr_re = r"<replacement +?id=[\'\"]([\w_-]+?)[\'\"]>(.+?)</replacement>"
replacementsdict = dict()
replacements_loaded = False  # nothing has been loaded, so just keep the original content


def load_replacements_file(filename: str):
    with open(filename, 'rt', encoding='utf8') as f:
        load_replacements_string(filename, f.read())


def load_replacements_string(context_filename: str, s: str):
    global replacementsdict, replacements_loaded
    for repl_id, body in re.findall(replacement_expr_re, s, flags=re.DOTALL):
        if repl_id in replacementsdict:
            b.warning(f"replacement '{repl_id}' is defined multiple times", file=context_filename)
        replacementsdict[repl_id] = body
    replacements_loaded = True


def get_replacement(context_filename: str, content: str, repl_id: str) -> str:
    global replacementsdict, replacements_loaded
    if not replacements_loaded:
        return content
    if repl_id not in replacementsdict:
        b.warning(f"replacement '{repl_id}' is not defined, using '????'", file=context_filename)
    return replacementsdict.get(repl_id, "????")
