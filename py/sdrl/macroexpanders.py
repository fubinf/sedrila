import functools
import os
import re

import base as b
import html
import sdrl.course
import sdrl.macros as macros
import sdrl.markdown as md

ALTDIR_KEYWORD = "ALT:"


def register_macros(course: sdrl.course.Coursebuilder):
    MM = macros.MM
    b.debug("registering macros")
    # ----- register EARLY-mode macros:
    macros.register_macro('INCLUDE', 1, MM.EARLY,
                          functools.partial(expand_include, course))
    # ----- register INNER-mode macros:
    macros.register_macro('HREF', 1, MM.INNER,
                          functools.partial(expand_href, course))  # show and link a URL
    macros.register_macro('PARTREF', 1, MM.INNER, 
                          functools.partial(expand_partref, course))  # slug as linktext
    macros.register_macro('PARTREFTITLE', 1, MM.INNER, 
                          functools.partial(expand_partref, course))  # title as linktext
    macros.register_macro('PARTREFMANUAL', 2, MM.INNER, 
                          functools.partial(expand_partref, course))  # explicit linktext
    macros.register_macro('TREEREF', 1, MM.INNER, 
                          functools.partial(expand_treeref, course))  # show full path in itree
    macros.register_macro('EC', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('EQ', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('ER', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('EREFC', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('EREFQ', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('EREFR', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('DIFF', 1, MM.INNER, sdrl.course.Taskbuilder.expand_diff)
    # ----- register hard-coded block macros:
    macros.register_macro('SECTION', 2, MM.BLOCKSTART, expand_section)
    macros.register_macro('ENDSECTION', 0, MM.BLOCKEND, expand_section)
    macros.register_macro('INNERSECTION', 2, MM.BLOCKSTART, expand_section)
    macros.register_macro('ENDINNERSECTION', 0, MM.BLOCKEND, expand_section)
    macros.register_macro('HINT', 1, MM.BLOCKSTART, expand_hint)
    macros.register_macro('ENDHINT', 0, MM.BLOCKEND, expand_hint)
    macros.register_macro('FOLDOUT', 1, MM.BLOCKSTART, expand_foldout)
    macros.register_macro('ENDFOLDOUT', 0, MM.BLOCKEND, expand_foldout)
    # ----- register generic block macros:
    generic_defs = {key: val for key, val in course.blockmacro_topmatter.items() if key.isupper()}
    for key, value in generic_defs.items():
        if "{arg2}" in value:
            args = 2
        elif "{arg1}" in value:
            args = 1
        else:
            args = 0
        macros.register_macro(key, args, MM.BLOCKSTART, expand_block)
        macros.register_macro(f'END{key}', 0, MM.BLOCKEND, expand_block)


def expand_href(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall) -> str:  # noqa
    return f"<a href='{macrocall.arg1}'>{macrocall.arg1}</a>"


def expand_partref(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall) -> str:
    part = course.get_part(macrocall.filename, macrocall.arg1)
    linktext = dict(PARTREF=part.slug, 
                    PARTREFTITLE=part.title, 
                    PARTREFMANUAL=macrocall.arg2)[macrocall.macroname]
    return f"<a href='{part.outputfile}' class='partref-link'>{html.escape(linktext)}</a>"


def expand_treeref(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall) -> str:
    actualpath = includefile_path(course, macrocall, itree_mode=True)
    showpath = actualpath[len(course.itreedir)+1:]  # skip itreedir part of path
    if not os.path.exists(actualpath):
        b.warning(f"{macrocall.macrocall_text}: itreedir file '{actualpath}' not found")
        showpath = "???"
    prefix = "<span class='treeref-prefix'></span>"
    mainpart = f"<span class='treeref'>{html.escape(showpath, quote=False)}</span>"
    suffix = "<span class='treeref-suffix'></span>"
    return f"{prefix}{mainpart}{suffix}"


def expand_section(macrocall: macros.Macrocall) -> str:
    """
    [SECTION::goal::subtype1,subtype2] etc.
    [INNERSECTION] is equivalent and serves for one level of proper nesting if needed.
    (Nesting [SECTION][ENDSECTION] blocks happens to work, but for the wrong reasons.)
    A section [SECTION]...[ENDSECTION] like the ahove gets rendered into the following structure:
    <div class='section section-goal'>
      <div class='section-subtypes section-goal-subtypes'>
        <div class='section-subtype section-goal-subtype1'>section_goal_subtype1_topmatter</div>
        <div class='section-subtype section-goal-subtype2'>section_goal_subtype2_topmatter</div>
      </div>
      section_goal_topmatter
      the entire body of the section block
    </div>
    """
    sectiontype = macrocall.arg1
    sectionsubtypes = macrocall.arg2
    if macrocall.macroname in ('SECTION', 'INNERSECTION'):
        r = []  # noqa, results list, to be join'ed
        r.append(f"<div class='section section-{sectiontype}'>")  # level 1
        r.append(f"<div class='section-subtypes section-{sectiontype}-subtypes'>")  # level 2
        subtypeslist = sectionsubtypes.split(",")
        for subtype in subtypeslist:
            matter = topmatter(macrocall, f'section_{sectiontype}_{subtype}')
            r.append(f"<div class='section-subtype section-{sectiontype}-{subtype}'>{matter}</div>")
        r.append("</div>")  # end level 2
        r.append(topmatter(macrocall, f'section_{sectiontype}'))
        return "\n".join(r)
    elif macrocall.macroname in ('ENDSECTION', 'ENDINNERSECTION'):
        return "</div>"
    assert False, macrocall  # impossible


def expand_hint(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'HINT':
        content = topmatter(macrocall, 'hint').format(arg1=macrocall.arg1)
        return f"<details class='blockmacro blockmacro-hint'><summary>\n{content}\n</summary>\n"
    elif macrocall.macroname == 'ENDHINT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_foldout(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'FOLDOUT':
        return f"<details class='blockmacro blockmacro-foldout'><summary>\n{macrocall.arg1}\n</summary>\n"
    elif macrocall.macroname == 'ENDFOLDOUT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_block(macrocall: macros.Macrocall) -> str:
    is_end = macrocall.macroname.startswith('END')
    macroname = (macrocall.macroname if not is_end else macrocall.macroname[3:])
    if is_end:
        return f"</div>"
    else:
        content = topmatter(macrocall, macroname).format(arg1=macrocall.arg1, arg2=macrocall.arg2)
        return f"<div class='blockmacro blockmacro-{macroname.lower()}'>\n{content}"


def expand_enumeration(macrocall: macros.Macrocall) -> str:
    macroname = macrocall.macroname
    classname = f"enumeration-{macroname.lower()}"
    value = macros.get_state(macroname) + 1
    macros.set_state(macroname, value)
    return f"<span class='{classname}'>{value}</span>"


def partswitch_enumeration(macroname: str, newpartname: str):  # noqa
    macros.set_state(macroname, 0)  # is independent of newpartname


def expand_enumerationref(macrocall: macros.Macrocall) -> str:
    # markup matches that of expand_enumeration(), argument is not checked in any way
    macroname = macrocall.macroname
    classname = f"enumeration-{macroname.lower()}"
    value = macrocall.arg1
    return f"<span class='{classname}'>{value}</span>"


def expand_include(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall) -> str:
    """
    [INCLUDE::filename] inserts file contents into the Markdown text.
    If the file has suffix *.md, it is macro-expanded beforehands,
    contents of all other files are inserted verbatim.
    A relative filename is relative to the location of the file containing the macro call.
    An absolute filename is relative to course.chapterdir.
    The format [INCLUDE::ALT:filename] refers to files in course.altdir,
    for relative names, the path from chapterdir to filename's dir is used below altdir.
    In the special case [INCLUDE::ALT:] with no filename at all, the filename is reused as well.
    """
    fullfilename = includefile_path(course, macrocall)
    # print(f"## fullfilename: {fullfilename} ({macrocall.filename})")
    if not os.path.exists(fullfilename):
        msgfunc = macrocall.warning if macrocall.arg1.startswith(ALTDIR_KEYWORD) else macrocall.error
        msgfunc(f"file '{fullfilename}' does not exist")  # noqa
        return ""
    with open(fullfilename, "rt", encoding='utf8') as f:
        rawcontent = f.read()
    macrocall.md.includefiles.add(fullfilename)  # record that we have included this file
    if fullfilename.endswith('.md'):
        return macros.expand_macros(md.md.context_sourcefile, md.md.partname, rawcontent)
    else:
        return rawcontent


def includefile_path(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall, itree_mode=False) -> str:
    """
    Normal mode constructs normal paths in chapterdir and those with prefix 'ALT:' in altdir.
    itree mode constructs normal paths in itreedir and warns about 'ALT:' prefix if present.
    """
    arg_re = r"(?P<alt>" + ALTDIR_KEYWORD + r")?(?P<slash>/)?(?P<incfile>.*)"
    mm = re.fullmatch(arg_re, macrocall.arg1)
    is_alt = mm.group("alt") is not None
    if is_alt and itree_mode:
        b.warning(f"{macrocall.macrocall_text}: '{ALTDIR_KEYWORD}' prefix makes no sense here")
        is_alt = False  # ignore the prefix
    is_abs = mm.group("slash") is not None
    inc_filepath = mm.group("incfile")  # e.g. ../chapterlevel_includefile
    ctx_filepath = macrocall.filename  # e.g. ch/chapter/group/task.md
    ctx_dirpath = os.path.dirname(ctx_filepath)  # e.g. ch/chapter/group
    ctx_basename = os.path.basename(ctx_filepath)  # e.g. task.md
    abs_topdir = (is_alt and course.altdir) or (itree_mode and course.itreedir) or course.chapterdir
    rel_dirpath = ctx_dirpath.replace(course.chapterdir, abs_topdir, 1)
    # print(f"## {macrocall.arg1} -> alt:{is_alt}, abs:{is_abs}, inc:{inc_filepath}, ctx:{ctx_dirpath}, "
    #       f"abs_topdir:{abs_topdir}, rel_dirpath:{rel_dirpath}")
    fullpath = os.path.join(abs_topdir if is_abs else rel_dirpath, inc_filepath or ctx_basename)
    return fullpath


def topmatter(macrocall: macros.Macrocall, name: str) -> str:
    topmatterdict = macrocall.md.blockmacro_topmatter  # noqa
    if name in topmatterdict:
        return topmatterdict[name]
    else:
        b.error("'%s', %s\n  blockmacro_topmatter '%s' is not defined in config" %
                (macrocall.filename, macrocall.macrocall_text, name))
        return ""  # neutral result
