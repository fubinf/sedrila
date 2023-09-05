"""Shortcut typenames, global constants, basic helpers."""
import json
import logging
import os
import enum
import sys
import typing as tg

import requests
import rich
import rich.table
import yaml

outstream = sys.stdout
num_errors = 0
loglevel = logging.ERROR
loglevels = dict(DEBUG=logging.DEBUG, INFO=logging.INFO, WARNING=logging.WARNING,
                 ERROR=logging.ERROR, CRITICAL=logging.CRITICAL)

CONFIG_FILENAME = "sedrila.yaml"  # plain filename, no directory possible
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrMap = tg.Mapping[str, str]
StrAnyMap = tg.Mapping[str, tg.Any]  # JSON or YAML structures


def set_loglevel(level: str):
    global loglevels, loglevel
    if level in loglevels:
        global loglevel
        loglevel = loglevels[level]
    else:
        pass  # simply ignore nonexisting loglevels


class Mode(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"


def as_fingerprint(raw: str) -> str:
    """Canonicalize fingerprint: all-lowercase, no blanks"""
    return raw.replace(' ', '').lower()


def copyattrs(context: str, source: StrAnyMap, target: tg.Any, 
              mustcopy_attrs: str, cancopy_attrs: str, mustexist_attrs: str, overwrite=True):
    """
    Copies data from YAML or JSON mapping 'd' to class object 'target' and checks attribute set of d.
    mustcopy_attrs, cancopy_attrs, and mustexist_attrs are comma-separated attribute name lists.
    mustcopy_attrs and cancopy_attrs are copied; mustcopy_attrs and mustexist_attrs must exist; 
    cancopy_attrs need not exist.
    If overwrite is False, fails if attribute already exists in target.
    Prints error and stops on problems.
    E.g. copyattrs(srcfile, yaml, self, "title,shorttitle,dir", "templatedir", "chapters")
    """
    def mysetattr(obj, name, value):
        if overwrite or not hasattr(target, name):
            setattr(obj, name, value)
    mustcopy_names = [a.strip() for a in mustcopy_attrs.split(',')]  # mandatory
    cancopy_names = [a.strip() for a in cancopy_attrs.split(',')]  # optional
    mustexist_names = [a.strip() for a in mustexist_attrs.split(',')]  # further mandatory
    source_names = set(source.keys())
    for m in mustcopy_names:  # transport these
        value = source.get(m, ValueError)
        if value is ValueError:
            error(f"{context}: required attribute is missing: {m}")
            exit_if_errors()
        else:
            mysetattr(target, m, value)
    for o in cancopy_names:  # transport these if present
        if o in source:
            mysetattr(target, o, source[o])
    extra_attrs = source_names - set(mustcopy_names) - set(cancopy_names) - set(mustexist_names)
    if extra_attrs:
        error(f"{context}: unexpected extra attributes found: {extra_attrs}")


def read_partsfile(self, file: str, text: str = None):
    """
    Reads files consisting of YAML metadata, then Markdown text, separated by a tiple-dash line.
    Stores metadata into self.metadata, rest into self.content.
    """
    SEPARATOR = "---\n"
    #----- obtain file contents:
    self.srcfile = file
    if not text:
        text = slurp(file)
    if SEPARATOR not in text:
        error(f"{self.srcfile}: triple-dash separator is missing")
        return
    self.metadata_text, self.content = text.split(SEPARATOR, 1)
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
    if loglevel <= logging.DEBUG:
        rich.print(msg)


def info(msg: str):
    if loglevel <= logging.INFO:
        rich.print(msg)


def warning(msg: str):
    if loglevel <= logging.WARNING:
        rich.print(f"[yellow]{msg}[/yellow]")


def error(msg: str):
    global num_errors
    num_errors += 1
    if loglevel <= logging.ERROR:
        rich.print(f"[red]{msg}[/red]")


def critical(msg: str):
    rich.print(f"[bold red]{msg}[/bold red]")
    sys.exit(num_errors)


def exit_if_errors(msg: str=""):
    if num_errors > 0:
        if msg:
            critical(msg)
        else:
            critical(f"==== {num_errors} error{'s' if num_errors != 1 else ''}. Exiting. ====")


def Table() -> rich.table.Table:
    """An empty Table in default sedrila style"""
    return rich.table.Table(show_header=True, header_style="bold yellow",
                            show_edge=False, show_footer=False)