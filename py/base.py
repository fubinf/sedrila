"""Shortcut typenames, global constants, basic helpers."""
import enum
import logging
import typing as tg

import yaml

logger = logging.getLogger()

CONFIG_FILENAME = "sedrila.yaml"  # plain filename, no directory possible
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrMap = tg.Mapping[str, str]
StrAnyMap = tg.Mapping[str, tg.Any]  # JSON or YAML structures


class Mode(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"


def copyattrs(d: StrAnyMap, target: tg.Any, mustcopy_attrs: str, cancopy_attrs: str, mustexist_attrs: str, overwrite=True):
    """
    Copies data from YAML or JSON mapping 'd' to class object 'target' and checks attribute set of d.
    mustcopy_attrs, cancopy_attrs, and mustexist_attrs are comma-separated attribute name lists.
    mustcopy_attrs and cancopy_attrs are copied; mustcopy_attrs and mustexist_attrs must exist; 
    cancopy_attrs need not exist.
    If overwrite is False, fails if attribute already exists in target.
    Raises ValueError on problems.
    E.g. copyattrs(yaml, self, "title,shorttitle,dir", "templatedir", "chapters")
    """
    def mysetattr(obj, name, value):
        if overwrite or not hasattr(target, name):
            setattr(obj, name, value)
    m_names = [a.strip() for a in mustcopy_attrs.split(',')]  # mandatory
    o_names = [a.strip() for a in cancopy_attrs.split(',')]  # optional
    f_names = [a.strip() for a in mustexist_attrs.split(',')]  # further mandatory
    d_names = set(d.keys())
    for m in m_names:  # transport these
        mysetattr(target, m, d[m])
    for o in o_names:  # transport these if present
        if o in d:
            mysetattr(target, o, d[o])
    extra_attrs = d_names - set(m_names) - set(o_names) - set(f_names)
    if extra_attrs:
        raise ValueError(f"unexpected extra attributes found: {extra_attrs}")


def read_partsfile(self, file: str, text: str = None):
    """
    Read file with 3+ double triple dash separated parts. Store parts data in self:
    part 1 in self.metadata_text and self.metadata,
    part 2 in self.content, part 3 in self.instructorcontent, parts 4..n in self.othercontents.
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
    self.instructorcontent = parts[2] 
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
