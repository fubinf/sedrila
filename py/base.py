"""Shortcut typenames, global constants, basic helpers."""
import logging
import typing as tg

import yaml

logger = logging.getLogger()

CONFIG_FILENAME = "sedrila.yaml"  # plain filename, no directory possible
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrMap = tg.Mapping[str, str]
StrAnyMap = tg.Mapping[str, tg.Any]  # JSON or YAML structures


def div(level: tg.Optional[int]) -> str:
    if level is None:
        return "<span>"
    else:
        return f"<div class='indent{max(level,4)}'>"


def div_end(level: tg.Optional[int]) -> str:
    if level is None:
        return "</span>"
    else:
        return f"</div>"


def read_and_check(d: StrAnyMap, target: tg.Any, m_attrs: str, o_attrs: str, f_attrs: str):
    """
    Transports data from YAML or JSON mapping 'd' to class object 'target' and checks attribute set of d.
    m_attrs, o_attrs, and f_attrs are comma-separated attribute name lists.
    m_attrs and o_attrs are transported; m_attrs and f_attrs must exist; o_attrs need not exist.
    Raises ValueError on problems.
    E.g. read_and_check(yaml, self, "title,shorttitle,dir", "templatedir", "chapters")
    """
    m_names = [a.strip() for a in m_attrs.split(',')]  # mandatory
    o_names = [a.strip() for a in o_attrs.split(',')]  # optional
    f_names = [a.strip() for a in f_attrs.split(',')]  # further mandatory
    d_names = set(d.keys())
    for m in m_names:  # transport these
        setattr(target, m, d[m])
    for o in o_names:  # transport these if present
        if o in d:
            setattr(target, o, d[o])
    extra_attrs = d_names - set(m_names) - set(o_names) - set(f_names)
    if extra_attrs:
        raise ValueError(f"unexpected extra attributes found: {extra_attrs}")


def read_partsfile(self, file: str, text: str = None):
    """
    Read file with 3+ double triple dash separated parts. Store parts data in self:
    part 1 in self.metadata_text and self.metadata,
    part 2 in self.content, part 3 in self.teachercontent, parts 4..n in self.othercontents.
    Complain if there are fewer than 3 parts or metadata is not YAML.
    """
    #----- obtain file contents:
    self.srcfile = file
    if not text:
        text = slurp(file)
    #----- store parts:
    parts = text.split("---\n---\n")
    if len(parts) < 3:
        raise ValueError("%s is not a parts file: must have three parts separated by double triple-dashes (found: %s)" %
                         (self.srcfile, len(parts)))
    self.metadata_text = parts[0]
    self.content = parts[1]
    self.teachercontent = parts[2] 
    self.othercontents = parts[3:]
    #----- parse metadata
    try:
        # ----- parse YAML data:
        self.metadata = yaml.safe_load(self.metadata_text)
    except yaml.YAMLError as exc:
        logger.error(f"{self.srcfile}: metadata YAML is malformed: {str(exc)}")


def slurp(filename: str) -> str:
    with open(filename, 'rt', encoding='utf8') as f:
        return f.read()


def spit(filename: str, content: str):
    with open(filename, 'wt', encoding='utf8') as f:
        f.write(content)
