import dataclasses
import functools
import os
import re

import base as b
import html
import sdrl.constants as c
import sdrl.course
import sdrl.macros as macros
import sdrl.markdown as md
import sdrl.snippetchecker as snippetchecker


def register_macros(course: sdrl.course.Coursebuilder):
    MM = macros.MM
    b.debug("registering macros")
    # ----- register EARLY-mode macros:
    macros.register_macro('INCLUDE', 1, MM.EARLY,
                          functools.partial(expand_include, course))
    macros.register_macro('SNIPPET', 2, MM.EARLY,
                          functools.partial(snippetchecker.expand_snippet_macro, course))
    # ----- register INNER-mode macros:
    macros.register_macro('HREF', 1, MM.INNER,
                          functools.partial(expand_href, course))  # show and link a URL
    macros.register_macro('PARTREF', 1, MM.INNER, 
                          functools.partial(expand_partref, course))  # name as linktext
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
    macros.register_macro('PROT', 1, MM.BLOCK, functools.partial(expand_prot, course))
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
    linktext = dict(PARTREF=part.name, 
                    PARTREFTITLE=part.title, 
                    PARTREFMANUAL=macrocall.arg2)[macrocall.macroname]
    return f"<a href='{part.outputfile}' class='partref-link'>{html.escape(linktext)}</a>"


def expand_treeref(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall) -> str:
    actualpath = includefile_path(course, macrocall, itree_mode=True)
    showpath = actualpath[len(course.itreedir)+1:]  # skip itreedir part of path
    if not os.path.exists(actualpath):
        b.warning(f"{macrocall.macrocall_text}: itreedir file '{actualpath}' not found",
                  file=macrocall.filename)
        showpath = "???"
    prefix = "<span class='treeref-prefix'></span>"
    mainpart = f"<span class='treeref'>{html.escape(showpath, quote=False)}</span>"
    suffix = "<span class='treeref-suffix'></span>"
    return f"{prefix}{mainpart}{suffix}"


def _register_encrypted_prot(course: sdrl.course.Coursebuilder, prot_filepath: str):
    """Register a .prot file to be encrypted and saved as .prot.crypt in the student directory."""
    import sdrl.elements as el
    # Get instructor fingerprints (only for instructors with pubkeys)
    keyfingerprints = [instructor['keyfingerprint']
                       for instructor in course.configdict['instructors']
                       if instructor.get('keyfingerprint', None) and instructor.get('pubkey', None)]
    if not keyfingerprints:
        b.debug(f"No instructor pubkeys with keyfingerprints found, skipping encryption of {prot_filepath}")
        return
    basename = os.path.basename(prot_filepath)
    outputname = f"{basename}.crypt"
    existing = course.directory.get_the(el.EncryptedProtFile, outputname)
    if existing:
        return
    course.directory.make_the(el.Sourcefile, prot_filepath)
    # Create encrypted protocol file element with isolated encryption
    b.debug(f"Registering encrypted prot file: {prot_filepath} -> {outputname}")
    try:
        pubkey_data = getattr(course, 'instructor_pubkeys', {})
        def transform_with_pubkeys(elem):
            return sdrl.course.Coursebuilder._transform_prot_file(elem, pubkey_data)
        elem = course.directory.make_the(
            el.EncryptedProtFile,
            outputname,
            sourcefile=prot_filepath,
            targetdir_s=course.targetdir_s,
            targetdir_i=course.targetdir_i,
            transformation=transform_with_pubkeys,
            fingerprints=keyfingerprints
        )
        b.debug(f"Successfully created EncryptedProtFile: {elem}")
    except Exception as e:
        b.error(f"Failed to create EncryptedProtFile {outputname}: {e}")
        import traceback
        b.error(traceback.format_exc())


def expand_prot(course: sdrl.course.Course, macrocall: macros.Macrocall) -> str:
    """[PROT::somedir/file.prot]. Plain paths in viewer mode, INCLUDE-style paths in author mode."""
    import sdrl.elements as el
    path = macrocall.arg1
    author_mode = isinstance(course, sdrl.course.Coursebuilder)  # in viewer mode we receive a dummy
    b.debug(f"expand_prot: {macrocall.arg1}, author_mode={author_mode}")
    if author_mode:
        assert isinstance(course, sdrl.course.Coursebuilder)
        path = includefile_path(course, macrocall, itree_mode=False)
        b.debug(f"expand_prot: resolved to {path}")
    if not os.path.exists(path):
        b.warning(f"{macrocall.macrocall_text}: file '{path}' not found", file=macrocall.filename)
        return f"\n<p>(('{path}' not found))</p>\n"
    content = b.slurp(path)
    macrocall.md.includefiles.add(path)  # record that we have included this file
    # In author mode, register encrypted version for instructor use
    if author_mode:
        b.debug(f"expand_prot: calling _register_encrypted_prot for {path}")
        _register_encrypted_prot(course, path)
    return prot_html(content)


def prot_html(content: str) -> str:
    @dataclasses.dataclass
    class State:
        s: int
        promptcount: int

    def promptmatch(the_line: str) -> re.Match:
        r"""
        Whether line is a shell prompt as prescribed by the SeDriLa course rules.
        Canonical prompt:  export PS1="\u@\h \w \t \!\n\$ "
        This is a two-line prompt. This routine considers the first line only.
        Prompts are copy-pasted as plaintext, so possible ANSI sequences for color are no longer present.
        The group names front, userhost, dir, time, num, back are part of the function interface 
        (i.e. the caller knows they all exist in any match and can use the group contents).
        """
        front_re = r"(?P<front>^.*?)"  # any stuff up front, e.g. '(myvenv)' 
        userhost_re = r"(?P<userhost>[-\+\w]+@[-\+\w]+)"  # user@host
        sep_re = r"\s+"
        dir_re = r"(?P<dir>[/~]\S*)"  # anything whitespace-less starting with '~' or '/'
        time_re = r"(?P<time>\d\d:\d\d:\d\d)"  # e.g. '14:03:59'
        num_re = r"(?P<num>\d+)"
        back_re = r"(?P<back>.*$)"  # any stuff in the back
        prompt_re = f"{front_re}{userhost_re}{sep_re}{dir_re}{sep_re}{time_re}{sep_re}{num_re}{back_re}"
        return re.fullmatch(prompt_re, the_line)

    def handle_promptmatch():  # uses mm, result, state. Corresponds to promptmatch().
        state.promptcount += 1
        state.s = PROMPTSEEN
        color_class = prompt_color(state.promptcount)
        promptindex = f"<span class='prot-counter {color_class}'>{state.promptcount}.</span>"
        front = f"<span class='vwr-front'>{esc('front')}</span>"
        userhost = f"<span class='vwr-userhost'>{esc('userhost')}</span>"
        dir = f"<span class='vwr-dir'>{esc('dir')}</span>"
        time = f"<span class='vwr-time'>{esc('time')}</span>"
        num = f"<span class='vwr-num'> {esc('num')} </span>"
        back = f"<span class='vwr-back'>{esc('back')}</span>"
        result.append(f"<tr><td>{promptindex} {front} {userhost} {dir} {time} {num} {back}</td></tr>")

    def esc(groupname: str) -> str:  # abbrev; uses mm
        return html.escape(mm.group(groupname))  # TODO_1_prechelt: make whitespace (indentation etc.) work

    def prompt_color(idx: int) -> str:
        # idx is 1-based command entry index
        if idx <= len(prompt_classes):
            return prompt_classes[idx - 1]
        return "prot-manual-color"
    result = ["\n<table class='vwr-table'>"]
    PROMPTSEEN, OUTPUT = (1, 2)
    state = State(s=OUTPUT, promptcount = 0)
    # Parse specs once (before filtering) to determine colors and spec blocks
    import sdrl.protocolchecker as protocolchecker
    import sdrl.markdown as md
    try:
        extractor = protocolchecker.ProtocolExtractor()
        proto = extractor.extract_from_content(content)
    except Exception:
        proto = protocolchecker.ProtocolFile("", [], 0)
    prompt_classes: list[str] = []
    manual_blocks: list[str] = []
    extra_blocks: list[str] = []
    error_blocks: list[list[str]] = []
    checker = protocolchecker.ProtocolChecker()
    for entry in proto.entries:
        rule = entry.check_rule
        color = "prot-manual-color"
        manuals = ""
        extras = ""
        errs: list[str] = []
        if rule and rule.skip:
            color = "prot-skip-color"
        elif rule and rule.manual:
            color = "prot-manual-color"
        else:
            # run automated check of author entry against itself to see if spec fits content
            try:
                result_check = checker._compare_entries(entry, entry)
                if result_check.success:
                    color = "prot-ok-color"
                else:
                    color = "prot-alert-color"
                    if not result_check.command_match:
                        label = f"command_re={rule.command_re}" if rule and rule.command_re else "command"
                        errs.append(f"<div class='prot-spec-error'><pre>{html.escape(label)}</pre> did not match</div>")
                    if not result_check.output_match:
                        label = f"output_re={rule.output_re}" if rule and rule.output_re else "output"
                        errs.append(f"<div class='prot-spec-error'><pre>{html.escape(label)}</pre> did not match</div>")
            except Exception:
                color = "prot-alert-color"
        if rule and rule.manual_text:
            manuals = f"<div class='prot-spec-manual'>{md.render_plain_markdown(rule.manual_text)}</div>"
        if rule and rule.extra_text:
            extras = f"<div class='prot-spec-extra'>{md.render_plain_markdown(rule.extra_text)}</div>"
        prompt_classes.append(color)
        manual_blocks.append(manuals)
        extra_blocks.append(extras)
        error_blocks.append(errs)
    # Filter out @PROT_SPEC markup before rendering
    content = protocolchecker.filter_prot_check_annotations(content)
    for line in content.split('\n'):
        line = line.rstrip()  # get rid of newline
        mm = promptmatch(line)
        if mm:
            handle_promptmatch()
        elif state.s == PROMPTSEEN:  # this is the command line
            idx = state.promptcount - 1
            if 0 <= idx < len(manual_blocks):
                if manual_blocks[idx]:
                    result.append(f"<tr><td>{manual_blocks[idx]}</td></tr>")
                if extra_blocks[idx]:
                    result.append(f"<tr><td>{extra_blocks[idx]}</td></tr>")
                for err in error_blocks[idx]:
                    result.append(f"<tr><td>{err}</td></tr>")
            result.append(f"<tr><td><span class='vwr-cmd'>{html.escape(line)}</span></td></tr>")
            state.s = OUTPUT
        elif state.s == OUTPUT:
            result.append(f"<tr><td><span class='vwr-output'>{html.escape(line)}</span></td></tr>")
        else:
            assert False
    result.append("</table>\n\n")
    return '\n'.join(result)


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
        r.append(f"<section class='section section-{sectiontype}'>")  # level 1
        r.append(f"<div class='section-subtypes section-{sectiontype}-subtypes'>")  # level 2
        subtypeslist = sectionsubtypes.split(",")
        for subtype in subtypeslist:
            matter = topmatter(macrocall, f'section_{sectiontype}_{subtype}')
            r.append(f"<div class='section-subtype section-{sectiontype}-{subtype}'>{matter}</div>")
        r.append("</div>")  # end level 2
        r.append(topmatter(macrocall, f'section_{sectiontype}'))
        return "\n".join(r)
    elif macrocall.macroname in ('ENDSECTION', 'ENDINNERSECTION'):
        return "</section>"
    assert False, macrocall  # impossible


def expand_hint(macrocall: macros.Macrocall) -> str:
    """[HINT::description what it is about]"""
    if macrocall.macroname == 'HINT':
        content = topmatter(macrocall, 'hint').format(arg1=macrocall.arg1)
        return f"<details class='blockmacro blockmacro-hint'><summary>\n{content}\n</summary>\n"
    elif macrocall.macroname == 'ENDHINT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_foldout(macrocall: macros.Macrocall) -> str:
    """[FOLDOUT]"""
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
    """[EC], [EQ], [ER]"""
    macroname = macrocall.macroname
    classname = f"enumeration-{macroname.lower()}"
    value = macros.get_state(macroname) + 1
    macros.set_state(macroname, value)
    return f"<span class='{classname}'>{value}</span>"


def partswitch_enumeration(macroname: str, newpartname: str):  # noqa
    macros.set_state(macroname, 0)  # is independent of newpartname


def expand_enumerationref(macrocall: macros.Macrocall) -> str:
    """[ECREF], [EQREF], [ERREF]"""
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
        msgfunc = macrocall.warning if macrocall.arg1.startswith(c.AUTHOR_ALTDIR_PREFIX) else macrocall.error
        msgfunc(f"file '{fullfilename}' does not exist")  # noqa
        return ""
    with open(fullfilename, "rt", encoding='utf8') as f:
        rawcontent = f.read()
    macrocall.md.includefiles.add(fullfilename)  # record that we have included this file
    if fullfilename.endswith('.md'):
        return macros.expand_macros(md.md.context_sourcefile, md.md.partname, rawcontent)
    elif fullfilename.endswith('.prot'):
        macrocall.error("Filename must not be *.prot. Call ignored. Use [PROT::...] for protocol files.")
        return ""  # ignore the entire macrocall
    else:
        return rawcontent


def includefile_path(course: sdrl.course.Coursebuilder, macrocall: macros.Macrocall, itree_mode=False) -> str:
    """
    Normal mode constructs normal paths in chapterdir, those with prefix 'ALT:' in altdir, and
    those with prefix 'ITREE:' in itreedir
    itree mode constructs normal paths in itreedir and warns about 'ALT:' or 'ITREE:' prefix if present.
    """
    keyword_re = f"{c.AUTHOR_ALTDIR_PREFIX}|{c.AUTHOR_ITREEDIR_PREFIX}"
    arg_re = r"(?P<kw>" + keyword_re + r")?(?P<slash>/)?(?P<incfile>.*)"
    mm = re.fullmatch(arg_re, macrocall.arg1)
    has_kw = mm.group("kw") is not None
    basedir = {None: course.chapterdir, 
               c.AUTHOR_ALTDIR_PREFIX: course.altdir, 
               c.AUTHOR_ITREEDIR_PREFIX: course.itreedir}
    if has_kw and itree_mode:
        b.warning(f"{macrocall.macrocall_text}: '{mm.group('kw')}' prefix makes no sense here",
                  file=macrocall.filename)
        has_kw = False  # ignore the prefix
    is_abs = mm.group("slash") is not None
    inc_filepath = mm.group("incfile")  # e.g. ../chapterlevel_includefile
    ctx_filepath = macrocall.filename  # e.g. ch/chapter/group/task.md
    ctx_dirpath = os.path.dirname(ctx_filepath)  # e.g. ch/chapter/group
    ctx_basename = os.path.basename(ctx_filepath)  # e.g. task.md
    abs_topdir = (itree_mode and course.itreedir) or basedir[mm.group("kw")]
    rel_dirpath = ctx_dirpath.replace(course.chapterdir, abs_topdir, 1)
    # print(f"## {macrocall.arg1} -> alt:{has_kw}, abs:{is_abs}, inc:{inc_filepath}, ctx:{ctx_dirpath}, "
    #       f"abs_topdir:{abs_topdir}, rel_dirpath:{rel_dirpath}")
    fullpath = os.path.join(abs_topdir if is_abs else rel_dirpath, inc_filepath or ctx_basename)
    return fullpath


def topmatter(macrocall: macros.Macrocall, name: str) -> str:
    topmatterdict = macrocall.md.blockmacro_topmatter  # noqa
    if name in topmatterdict:
        return topmatterdict[name]
    else:
        b.error(f"{macrocall.macrocall_text}: blockmacro_topmatter '{name}' is not defined in config",
                file=macrocall.filename)
        return ""  # neutral result
