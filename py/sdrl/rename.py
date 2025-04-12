"""
Heuristic 'rename' refactoring on SeDriLa courses:
- given an old and a new partname,
- rename all matching dirs first (exploiting the fact that partnames are globally unique,
  even across part types),
- rename all matching files
- apply precise replacements in *.md files:
  mentions in 'assumes:', 'requires:', PARTREF, INCLUDE, PROT, TREEREF.
- apply heuristic replacements in newpartname.prot files:
  What looks like a matching dir name (having slashes) or file name (having a suffix)
  gets replaced. Bare-word matches get reported.
- This may produce some false positive dir+file renames, especially for short or generic oldpartnames.
- It will produce false negatives for textual mentions in *.md (rare), *.prot (sometimes),
  and all other source files (common), so a fulltext textual search should be done after a rename
  to fix remaining mentions.
"""

import os
import re
import shutil

import base as b


class _Collector:
    """Collect first files (for processing) and then replacements (for reporting)."""
    files_renamed: list[str]
    dirs_renamed: list[str]
    md_files: list[str]
    prot_files: list[str]
    headers_replaced: dict[str, str]
    macros_replaced: dict[str, str]
    protlines_replaced: dict[str, str]

    def __init__(self):
        self.files_renamed = []
        self.dirs_renamed = []
        self.md_files = []
        self.prot_files = []
        self.headers_replaced = dict()
        self.macros_replaced = dict()
        self.protlines_replaced = dict()

    def record(self, whichdict: str, filepath: str, line: str):
        thedict = getattr(self, whichdict)
        if filepath not in thedict:
            thedict[filepath] = []
        thedict[filepath].append(line)

def rename_part(chapterdir, altdir, itreedir, old_partname, new_partname):
    collector = _Collector()
    _rename_and_collect_across(chapterdir, old_partname, new_partname, collector)
    _rename_and_collect_across(altdir, old_partname, new_partname, collector)
    _rename_and_collect_across(itreedir, old_partname, new_partname, collector)
    _process_markdown_files(collector, old_partname, new_partname)
    _process_prot_files(collector, old_partname, new_partname)
    _report_outcomes(collector, old_partname, new_partname)


def _rename_and_collect_across(root: str, oldname: str, newname: str, collector: _Collector):
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # ----- rename matching subdirs, skip invisible ones:
        skip_these: list[int] = []
        for i in range(len(dirnames)):
            dirname = dirnames[i]  # abbrev
            if dirname == oldname:
                filepath = os.path.join(dirpath, oldname)
                new_filepath = os.path.join(dirpath, newname)
                shutil.move(filepath, new_filepath)  # rename dir
                dirnames[i] = newname  # send os.walk into renamed dir
                collector.dirs_renamed.append(new_filepath)
            elif dirname.startswith('.'):
                skip_these.append(i)
        for i in reversed(skip_these):  # make os.walk skip these subdirs 
            del dirnames[i]
        # ----- rename matching files, collect files for processing:
        for filename in filenames:
            basename, suffix = os.path.splitext(filename)
            filepath = os.path.join(dirpath, filename)
            # --- process matching files:
            if basename == oldname:
                new_filepath = os.path.join(dirpath, f"{newname}{suffix}")
                shutil.move(filepath, new_filepath)
                collector.files_renamed.append(new_filepath)
                filepath = new_filepath
                if filepath.endswith('.prot'):
                    collector.prot_files.append(filepath)
            # --- collect all markdown files:
            if filepath.endswith('.md'):
                collector.md_files.append(filepath)


def _process_markdown_files(collector: _Collector, oldname: str, newname: str):
    for filepath in collector.md_files:
        filecontents = b.slurp(filepath)
        lines = filecontents.split('\n')
        replacements = 0  # discriminate files with changes from those without
        for i, line in enumerate(lines):
            line2 = _replace_requires_assumes(line, oldname, newname)
            if line2 != line:
                collector.record('headers_replaced', filepath, line2) 
            line3 = _replace_macros(line2, oldname, newname)
            if line3 != line2:
                collector.record('macros_replaced', filepath, line3)
            if line3 != line:
                lines[i] = line3
                replacements += 1
        if replacements > 0:
            filecontents = '\n'.join(lines)
            b.spit(filepath, filecontents)


def _replace_requires_assumes(line: str, oldname: str, newname: str):
    # the partname is delimited by colon, blank, comma, or end-of-line:
    regexp = rf'^(requires:|assumes:)(.*[, ]|){re.escape(oldname)}([, ]|$)'
    return re.sub(regexp, lambda m: fr"{m.group(1)}{m.group(2)}{newname}{m.group(3)}", line)


def _replace_macros(line: str, oldname: str, newname: str):
    def replacement(m: re.Match):
        if len(m.group('nil1')) > 0 or len(m.group('nil2')) > 0:
            return m.group()  # not actually a match!
        return f"[{m.group('cmd')}{m.group('stuff1')}{newname}{m.group('stuff2')}]"

    line = line.replace(f"[PARTREF::{oldname}]", f"[PARTREF::{newname}]")
    line = line.replace(f"[PARTREFTITLE::{oldname}]", f"[PARTREFTITLE::{newname}]")
    line = line.replace(f"[PARTREFMANUAL::{oldname}::", f"[PARTREFMANUAL::{newname}::")
    # a partname is a greedy match to r'[-\w]+', so in a match to
    # rf'([-\w]*)({re.escape(oldname)})([-\w]*)' for which groups 1 and 3 are empty, is a partname match.
    # stuff before and after in the path can be anything except closing bracket: r'[^\]]*' (non-greedy).
    stuff1 = r'(?P<stuff1>[^\]]*?)'
    stuff2 = r'(?P<stuff2>[^\]]*?)'
    nil1 = r'(?P<nil1>[-\w]*)'
    nil2 = r'(?P<nil2>[-\w]*)'
    core = rf'(?P<core>{re.escape(oldname)})'
    pathexp = f"{stuff1}{nil1}{core}{nil2}{stuff2}"
    cmds = ('INCLUDE::', 'INCLUDE::ALT:', 'PROT::', 'PROT::ALT:', 'TREEREF::')
    for cmd in cmds:
        regexp = rf'\[(?P<cmd>{cmd}){pathexp}\]'
        line = re.sub(regexp, replacement, line)
    return line


def _process_prot_files(collector: _Collector, oldname: str, newname: str):
    for filepath in collector.prot_files:
        filecontents = b.slurp(filepath)
        lines = filecontents.split('\n')
        replacements = 0  # discriminate files with changes from those without
        for i, line in enumerate(lines):
            orig_line = line
            line = _replace_protline(line, oldname, newname)
            if line != orig_line:
                collector.record('protlines_replaced', filepath, line)
                lines[i] = line
                replacements += 1
        if replacements > 0:
            filecontents = '\n'.join(lines)
            b.spit(filepath, filecontents)


def _replace_protline(line: str, oldname: str, newname: str):
    """replace any match that is not surrounded by partname-ish chars; see _replace_macros()"""
    def replacement(m: re.Match):
        if len(m.group('nil1')) > 0 or len(m.group('nil2')) > 0:
            return m.group()  # not actually a match!
        return newname

    nil1 = r'(?P<nil1>[-\w]*)'
    nil2 = r'(?P<nil2>[-\w]*)'
    core = rf'(?P<core>{re.escape(oldname)})'
    regexp = f"{nil1}{core}{nil2}"
    return re.sub(regexp, replacement, line)


def _report_outcomes(collector: _Collector, oldname: str, newname: str):
    if collector.dirs_renamed:
        b.info("############ Directories renamed:")
        b.warning('\n'.join(collector.dirs_renamed))
    if collector.files_renamed:
        b.info("############ Files renamed:")
        b.warning('\n'.join(collector.files_renamed))
    if len(collector.headers_replaced) > 0:
        thedict = collector.headers_replaced
        b.info("############ requires/assumes headers replaced in *.md:")
        for path in sorted(thedict.keys()):
            b.info(f"--- {path}")
            b.warning('\n'.join(sorted(thedict[path])))
    if len(collector.macros_replaced) > 0:
        thedict = collector.macros_replaced
        b.info("############ macro calls replaced in *.md:")
        for path in sorted(thedict.keys()):
            b.info(f"--- {path}")
            for line in sorted(thedict[path]):
                startpos = line.find('[')
                b.warning(line[startpos:])
    if len(collector.protlines_replaced) > 0:
        thedict = collector.protlines_replaced
        b.info(f"############ replacements in {newname}.prot:")
        for path in sorted(thedict.keys()):
            b.info(f"--- {path}")
            b.warning('\n'.join(sorted(thedict[path])))
