"""Shortcut typenames, global constants, basic helpers."""
import enum
import json
import logging
import re
import time
import typing as tg

import requests
import rich
import rich.progress
import rich.table
import yaml


starttime = time.time()
num_errors = 0
msgs_seen = set()
loglevel = logging.ERROR
loglevels = dict(DEBUG=logging.DEBUG, INFO=logging.INFO, WARNING=logging.WARNING,
                 ERROR=logging.ERROR, CRITICAL=logging.CRITICAL)
register_files_callback: tg.Callable[[str], None]

OStr = tg.Optional[str]
StrAnyDict = dict[str, tg.Any]  # JSON or YAML structures


def set_loglevel(level: str):
    global loglevels, loglevel
    if level in loglevels:
        global loglevel
        loglevel = loglevels[level]
    else:
        pass  # simply ignore nonexisting loglevels


def set_register_files_callback(callback: tg.Callable[[str], None]):
    global register_files_callback
    register_files_callback = callback


class Mode(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"


class CritialError(Exception):
    pass

def as_fingerprint(raw: str) -> str:
    """Canonicalize fingerprint: all-lowercase, no blanks"""
    return raw.replace(' ', '').lower()


def copyattrs(context: str, source: StrAnyDict, target: tg.Any, 
              mustcopy_attrs: str, cancopy_attrs: str, mustexist_attrs: str, 
              typecheck: dict[str, type]=dict(), overwrite=True, report_extra=False):  # noqa
    """
    Copies data from YAML or JSON mapping 'source' to class object 'target' and checks attribute set of d.
    mustcopy_attrs, cancopy_attrs, and mustexist_attrs are comma-separated attribute name lists.
    mustcopy_attrs and cancopy_attrs are copied; mustcopy_attrs and mustexist_attrs must exist; 
    cancopy_attrs need not exist.
    typecheck defines types for attrs that must not be str.
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
    for mname in mustcopy_names:  # transport these
        value = source.get(mname, ValueError)
        if value is ValueError:
            error(f"{context}: required attribute is missing: {mname}")
            finalmessage()
        else:
            mysetattr(target, mname, value)
    for cname in cancopy_names:  # transport these if present, set them to None if not
        if cname in source:
            if hasattr(target, cname) and not overwrite:
                warning("%s: %soverwriting '%s': old value '%s', new value '%s'" %
                        (context, "" if overwrite else "not ", cname, getattr(target, cname), source[cname]))
            mysetattr(target, cname, source[cname])
        elif cname not in source and not hasattr(target, cname):
            setattr(target, cname, None)
    extra_attrs = source_names - set(mustcopy_names) - set(cancopy_names) - set(mustexist_names)
    if report_extra and extra_attrs:
        warning(f"unexpected extra attributes found: {extra_attrs}", file=context)
    for attrname, its_type in typecheck.items():
        value = getattr(target, attrname, None)
        if value and not isinstance(value, its_type):
            error(f"'{context}': attribute '{attrname}' should be {str(its_type)} (is '{value}')")


def slurp(resource: str) -> str:
    """Reads local file (via filename) or http resource (via URL)."""
    try:
        if resource.startswith('http:') or resource.startswith('https://'):
            response = requests.get(resource)
            return response.text
        else:
            with open(resource, 'rt', encoding='utf8') as f:
                return f.read()
    except:  # noqa
        critical(f"'{resource}' does not exist")


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


def slugify(value: str) -> str:
    """ Slugify a string, to make it URL friendly. """
    separator = "-"
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[{}\s]+'.format(separator), separator, value)


def debug(msg: str):
    if loglevel <= logging.DEBUG:
        rich_print(msg)


def info(msg: str):
    if loglevel <= logging.INFO:
        rich_print(msg, "green")


def warning(msg: str, file: str = None, file2: str = None):
    if loglevel <= logging.WARNING:
        msg = _process_params(msg, file, file2)
        rich_print(msg, "yellow")


def error(msg: str, file: str = None, file2: str = None):
    if loglevel <= logging.ERROR:
        msg = _process_params(msg, file, file2)
        rich_print(msg, "red", count=1)


def critical(msg: str):
    rich_print(msg, "bold red", count=1)
    raise CritialError(msg)


def finalmessage():
    timing = "%.1f seconds" % (time.time() - starttime)
    if num_errors > 0:
        critical(f"==== {num_errors} error{'s' if num_errors != 1 else ''}. {timing}. Exiting. ====")
    else:
        info(f"::: {timing} :::")


def caller(how_far_up: int = 1) -> str:
    """Returns 'functionname:lineno' for how_far_up frames above the caller: the caller's n-th caller"""
    import inspect as sp
    frame = sp.currentframe().f_back  # the caller's frame
    for k in range(how_far_up):
        frame = frame.f_back
    return f"{frame.f_code.co_qualname}:{frame.f_lineno}"


def plural_s(number, value="s") -> str:
    return value if number != 1 else ""


def Table() -> rich.table.Table:
    """An empty Table in default sedrila style"""
    return rich.table.Table(show_header=True, header_style="bold yellow",
                            show_edge=False, show_footer=False)


def get_progressbar(maxcount: int) -> tg.Iterator[rich.progress.ProgressType]:
    return iter(rich.progress.track(range(maxcount), description="", transient=True, ))


def rich_print(msg: str, enclose_in_tag: tg.Optional[str] = None, count = 0):
    """Print any message, but each one only once."""
    global num_errors, msgs_seen
    if msg not in msgs_seen:
        msgs_seen.add(msg)
        num_errors += count
        if enclose_in_tag:
            msg = f"[{enclose_in_tag}]{msg}[/{enclose_in_tag}]"            
        rich.print(msg)


def _process_params(msg: str, file: tg.Optional[str], file2: tg.Optional[str]):
    if file and file2:
        msg = f"Files '{file}' and '{file2}':\n   {msg}"
        register_files_callback(file)
        register_files_callback(file2)
    elif file:
        msg = f"File '{file}':\n   {msg}"
        register_files_callback(file)
    return msg


def _testmode_reset():
    """reset error counter; avoid text wrapping of b.error() etc."""
    global num_errors, msgs_seen, starttime
    starttime = time.time()
    num_errors = 0
    msgs_seen = set()
    rich.get_console()._width = 10000
    set_register_files_callback(lambda s: None)