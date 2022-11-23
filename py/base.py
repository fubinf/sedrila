"""Shortcut typenames, global constants, basic helpers."""
import json
import os
import enum
import sys
import typing as tg

import requests
import yaml

outstream = sys.stdout
num_errors = 0

CONFIG_FILENAME = "sedrila.yaml"  # plain filename, no directory possible
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrMap = tg.Mapping[str, str]
StrAnyMap = tg.Mapping[str, tg.Any]  # JSON or YAML structures


class Mode(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"


def as_fingerprint(raw: str) -> str:
    """Canonicalize fingerprint: all-lowercase, no blanks"""
    return raw.replace(' ', '').lower()


def copyattrs(source: StrAnyMap, target: tg.Any, mustcopy_attrs: str, cancopy_attrs: str, mustexist_attrs: str, overwrite=True):
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
    mustcopy_names = [a.strip() for a in mustcopy_attrs.split(',')]  # mandatory
    cancopy_names = [a.strip() for a in cancopy_attrs.split(',')]  # optional
    mustexist_names = [a.strip() for a in mustexist_attrs.split(',')]  # further mandatory
    source_names = set(source.keys())
    for m in mustcopy_names:  # transport these
        mysetattr(target, m, source[m])
    for o in cancopy_names:  # transport these if present
        if o in source:
            mysetattr(target, o, source[o])
    extra_attrs = source_names - set(mustcopy_names) - set(cancopy_names) - set(mustexist_names)
    if extra_attrs:
        raise ValueError(f"unexpected extra attributes found: {extra_attrs}")


def read_partsfile(self, file: str, text: str = None):
    """
    Supports reading two different formats.

    Legacy format with 3+ double triple dash separated parts. Store parts data in self:
    part 1 in self.metadata_text and self.metadata,
    part 2 in self.content, part 3 in self.instructorcontent, parts 4..n in self.othercontents.
    Complain if there are fewer than 3 parts or metadata is not YAML.

    The new format will handle different types based on admonitions. Metadata is separated by a blank line
    """
    #----- obtain file contents:
    self.srcfile = file
    if not text:
        text = slurp(file)
    #----- store parts:
    parts = text.split("---\n---\n")
    if len(parts) >= 3: #legacy mode
        self.metadata_text = parts[0]
        self.content = parts[1]
        self.instructorcontent = parts[2] 
        self.othercontents = parts[3:]
    else:
        #this assumes that metadata will always be present, but that should not be an issue
        self.metadata_text, self.content = text.split(os.linesep + os.linesep, 1)
        self.instructorcontent = None
    #----- parse metadata
    try:
        # ----- parse YAML data:
        self.metadata = yaml.safe_load(self.metadata_text)
    except yaml.YAMLError as exc:
        error(f"{self.srcfile}: metadata YAML is malformed: {str(exc)}")


def slurp(resource: str) -> str:
    """Reads local file (via filename) or http resource (via URL)."""
    if resource.startswith('http:') or resource.startswith('https://'):
        response = requests.get(resource)
        return response.text
    else:
        with open(resource, 'rt', encoding='utf8') as f:
            return f.read()


def slurp_json(resource: str) -> StrAnyMap:
    return json.loads(slurp(resource))


def slurp_yaml(resource: str) -> StrAnyMap:
    return yaml.safe_load(slurp(resource))


def spit(filename: str, content: str):
    with open(filename, 'wt', encoding='utf8') as f:
        f.write(content)


def spit_json(filename: str, content: StrAnyMap):
    spit(filename, json.dumps(content))


def spit_yaml(filename: str, content: StrAnyMap):
    spit(filename, yaml.safe_dump(content))


def debug(msg: str):
    # print(msg)
    pass


def info(msg: str):
    print(msg)


def warning(msg: str):
    print(msg)


def error(msg: str):
    global num_errors
    num_errors += 1
    print(msg)


def critical(msg: str):
    print(msg)
    sys.exit(num_errors)


def exit_if_errors(msg: str=""):
    if num_errors > 0:
        critical(f"{num_errors} error{'s' if num_errors else ''}. Exiting.")
