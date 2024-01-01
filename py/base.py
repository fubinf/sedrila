"""Shortcut typenames, global constants, basic helpers."""
import json
import logging
import enum
import sys
import typing as tg

import requests
import rich
import rich.table
import yaml

outstream = sys.stdout
num_errors = 0
msgs_seen = set()
loglevel = logging.ERROR
loglevels = dict(DEBUG=logging.DEBUG, INFO=logging.INFO, WARNING=logging.WARNING,
                 ERROR=logging.ERROR, CRITICAL=logging.CRITICAL)

CONFIG_FILENAME = "sedrila.yaml"  # at top-level of source dir
METADATA_FILE = "course.json"  # at top-level of build directory
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrAnyDict = dict[str, tg.Any]  # JSON or YAML structures


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


def copyattrs(context: str, source: StrAnyDict, target: tg.Any, 
              mustcopy_attrs: str, cancopy_attrs: str, mustexist_attrs: str, overwrite=True):
    """
    Copies data from YAML or JSON mapping 'source' to class object 'target' and checks attribute set of d.
    mustcopy_attrs, cancopy_attrs, and mustexist_attrs are comma-separated attribute name lists.
    mustcopy_attrs and cancopy_attrs are copied; mustcopy_attrs and mustexist_attrs must exist; 
    cancopy_attrs need not exist.
    If overwrite is False, fails if attribute already exists in target.
    Prints error and stops on problems, using 'context' as location info in the error message.
    E.g. copyattrs(sourcefile, yaml, self, "title,shorttitle,dir", "templatedir", "chapters")
    """
    def mysetattr(obj, name, newvalue):
        if overwrite or not hasattr(target, name):
            setattr(obj, name, newvalue)
    def names_in(attrlist: str) -> list[str]:
        if not attrlist:
            return []
        return [a.strip() for a in attrlist.split(',')]
    mustcopy_names = names_in(mustcopy_attrs)  # mandatory
    cancopy_names = names_in(cancopy_attrs)  # optional
    mustexist_names = names_in(mustexist_attrs)  # further mandatory
    if not source:
        source = dict()
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
            if hasattr(target, o) and not overwrite:
                warning("%s: %soverwriting '%s': old value '%s', new value '%s'" %
                        (context, "" if overwrite else "not ", o, getattr(target, o), source[o]))
            mysetattr(target, o, source[o])
    extra_attrs = source_names - set(mustcopy_names) - set(cancopy_names) - set(mustexist_names)
    if extra_attrs:
        error(f"{context}: unexpected extra attributes found: {extra_attrs}")


def slurp(resource: str) -> str:
    """Reads local file (via filename) or http resource (via URL)."""
    if resource.startswith('http:') or resource.startswith('https://'):
        response = requests.get(resource)
        return response.text
    else:
        with open(resource, 'rt', encoding='utf8') as f:
            return f.read()


def slurp_json(resource: str) -> StrAnyDict:
    return json.loads(slurp(resource))


def slurp_yaml(resource: str) -> StrAnyDict:
    return yaml.safe_load(slurp(resource))


def spit(filename: str, content: str):
    with open(filename, 'wt', encoding='utf8') as f:
        f.write(content)


def spit_json(filename: str, content: StrAnyDict):
    spit(filename, json.dumps(content))


def spit_yaml(filename: str, content: StrAnyDict):
    spit(filename, yaml.safe_dump(content))


def debug(msg: str):
    if loglevel <= logging.DEBUG:
        _rich_print(msg)


def info(msg: str):
    if loglevel <= logging.INFO:
        _rich_print(msg)


def warning(msg: str):
    if loglevel <= logging.WARNING:
        _rich_print(f"[yellow]{msg}[/yellow]")


def error(msg: str):
    global num_errors, msgs_seen
    if msg not in msgs_seen:
        num_errors += 1
    if loglevel <= logging.ERROR:
        _rich_print(f"[red]{msg}[/red]")


def critical(msg: str):
    global num_errors
    num_errors += 1
    _rich_print(f"[bold red]{msg}[/bold red]")
    sys.exit(num_errors)


def exit_if_errors(msg: str = ""):
    if num_errors > 0:
        if msg:
            critical(msg)
        else:
            critical(f"==== {num_errors} error{'s' if num_errors != 1 else ''}. Exiting. ====")


def Table() -> rich.table.Table:
    """An empty Table in default sedrila style"""
    return rich.table.Table(show_header=True, header_style="bold yellow",
                            show_edge=False, show_footer=False)


def _rich_print(msg: str):
    """Print any message, but each one only once."""
    global msgs_seen
    if msg not in msgs_seen:
        msgs_seen.add(msg)
        rich.print(msg)
