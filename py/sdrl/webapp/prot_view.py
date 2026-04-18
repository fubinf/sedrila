"""Protocol file rendering: comparison (instructor) and plain (student) views."""
import dataclasses
import html
import os
import tempfile
import textwrap

import requests

import base as b
import sdrl.markdown as md
import sdrl.participant


def render_prot_compare(
    workdir_top: str,
    relpath: str,
    student_content: str,
    author_content: str | None,
    author_source: str | None = None,
) -> str:
    """
    Render protocol comparison (student vs author) with colors per spec:
    - ok -> prot-ok-color
    - fail -> prot-alert-color
    - manual -> prot-manual-color
    - skip -> prot-skip-color

    Also renders prompt lines with colored numbers.
    """
    import sdrl.protocolchecker as protocolchecker

    @dataclasses.dataclass
    class State:
        s: int
        promptcount: int

    def handle_promptmatch(color_class: str):  # uses mm, result, state
        state.promptcount += 1
        state.s = PROMPTSEEN
        # Instructor view: show prompt number WITH color
        promptindex = f"<span class='prot-counter {color_class}'>{state.promptcount}.</span>"
        front = f"<span class='vwr-front'>{esc('front')}</span>"
        userhost = f"<span class='vwr-userhost'>{esc('userhost')}</span>"
        dir = f"<span class='vwr-dir'>{esc('dir')}</span>"
        time = f"<span class='vwr-time'>{esc('time')}</span>"
        num = f"<span class='vwr-num'> {esc('num')} </span>"
        back = f"<span class='vwr-back'>{esc('back')}</span>"
        result.append(f"<tr><td>{promptindex} {front} {userhost} {dir} {time} {num} {back}</td></tr>")

    def esc(groupname: str) -> str:  # abbrev; uses mm
        return html.escape(mm.group(groupname))

    checker = protocolchecker.ProtocolChecker()
    extractor = protocolchecker.ProtocolExtractor()
    prompt_regex = extractor.prompt_regex
    student_file = os.path.join(workdir_top, relpath.lstrip("/"))
    # If author content cannot be loaded (encrypted file not decryptable), show error
    if author_content is None:
        return ("\n<p style='color: red; background-color: #ffe6e6; padding: 10px;'>"
                "<strong>\u26a0 Comparison not available: </strong>"
                "Author protocol file is encrypted and cannot be decrypted. "
                "Only instructors with the private key can view this comparison.</p>\n")

    def compare_results() -> list[protocolchecker.CheckResult]:
        # Always use temporary file approach since author content may be from encrypted source
        with tempfile.NamedTemporaryFile(mode="w", suffix=".prot", delete=False) as tmp:
            tmp.write(author_content or "")
            tmp.flush()
            tmp_path = tmp.name
        try:
            return checker.compare_files(student_file, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    results = compare_results()

    def color_for(res: protocolchecker.CheckResult) -> str:
        rule = res.author_entry.check_rule if res.author_entry else None
        if rule and rule.skip:
            return "prot-skip-color"
        # Check if there are automated checks (regex rules)
        has_automated_check = rule and (rule.command_re or rule.output_re)
        if has_automated_check:
            # If there are automated checks, use their results (green/red)
            # manual= is just additional information, doesn't affect the color
            if res.success:
                return "prot-ok-color"
            else:
                return "prot-alert-color"
        else:
            if res.requires_manual_check:
                return "prot-manual-color"
            if not res.success:
                return "prot-alert-color"
            return "prot-manual-color"
    prompt_colors = [color_for(res) for res in results]
    result = ["\n<table class='vwr-table'>"]
    PROMPTSEEN, OUTPUT = (1, 2)
    state = State(s=OUTPUT, promptcount=0)
    # Filter out @PROT_SPEC and @TEST_SPEC annotations before rendering
    import sdrl.programchecker as programchecker_mod
    content = protocolchecker.filter_prot_check_annotations(student_content)
    content = programchecker_mod.filter_program_check_annotations(content)
    for line in content.split('\n'):
        line = line.rstrip()
        # Force sync point: command line starting with $
        if line.lstrip().startswith('$'):
            idx = state.promptcount - 1
            # Show manual/extra/error blocks before the command
            if 0 <= idx < len(results):
                res = results[idx]
                rule = res.author_entry.check_rule if res.author_entry else None
                if rule and rule.manual_text:
                    result.append(f"<tr><td><div class='prot-spec-manual'>"
                                  f"{md.render_plain_markdown(rule.manual_text)}</div></td></tr>")
                if rule and rule.extra_text:
                    result.append(f"<tr><td><div class='prot-spec-extra'>"
                                  f"{md.render_plain_markdown(rule.extra_text)}</div></td></tr>")
                # Show error information and expected values
                if not res.success and res.error_message:
                    error_html = f"<div class='prot-spec-error'><pre>{html.escape(res.error_message)}</pre>"
                    if res.author_entry:
                        error_html += (f"<div class='prot-spec-hint' style='margin-top: 10px;'>"
                                       f"<strong>Expected command:</strong><br>"
                                       f"<code>{html.escape(res.author_entry.command)}</code>")
                        if res.author_entry.output:
                            author_output_escaped = html.escape(res.author_entry.output)
                            error_html += textwrap.dedent(f"""<br><br><details>
                                <summary><strong>Expected output (click to expand)</strong></summary>
                                <pre class='prot-spec-code'>{author_output_escaped}</pre>
                                </details>""").strip()
                        error_html += "</div>"
                    error_html += "</div>"
                    result.append(f"<tr><td>{error_html}</td></tr>")
                elif not res.success:
                    # show right command
                    if rule and rule.command_re and not res.command_match:
                        hint_html = f"<div class='prot-spec-error'>command_re did not match: <pre>{html.escape(rule.command_re)}</pre>"
                        if res.author_entry:
                            hint_html += f"<div class='prot-spec-hint' style='margin-top: 10px;'><strong>Standard command:</strong><br><code>{html.escape(res.author_entry.command)}</code></div>"
                        hint_html += "</div>"
                        result.append(f"<tr><td>{hint_html}</td></tr>")
                    # show right output
                    if rule and rule.output_re and not res.output_match:
                        hint_html = f"<div class='prot-spec-error'>output_re did not match: <pre>{html.escape(rule.output_re)}</pre>"
                        if res.author_entry:
                            author_output_escaped = html.escape(res.author_entry.output)
                            hint_html += textwrap.dedent(f"""<div class='prot-spec-hint' style='margin-top: 10px;'>
                                <details>
                                <summary><strong>Standard output (click to expand)</strong></summary>
                                <pre class='prot-spec-code'>{author_output_escaped}</pre>
                                </details>
                                </div>""").strip()
                        hint_html += "</div>"
                        result.append(f"<tr><td>{hint_html}</td></tr>")
                # show right command and output to help the instructor for review
                if res.requires_manual_check and res.author_entry:
                    hint_html = "<div class='prot-spec-hint'><strong>Reference for manual check:</strong><br><br>"
                    hint_html += f"<strong>Expected command:</strong><br><code>{html.escape(res.author_entry.command)}</code>"
                    if res.author_entry.output:
                        author_output_escaped = html.escape(res.author_entry.output)
                        hint_html += textwrap.dedent(f"""<br><br><details>
                            <summary><strong>Expected output (click to expand)</strong></summary>
                            <pre class='prot-spec-code'>{author_output_escaped}</pre>
                            </details>""").strip()
                    hint_html += "</div>"
                    result.append(f"<tr><td>{hint_html}</td></tr>")
            result.append(f"<tr><td><span class='vwr-cmd'>{html.escape(line)}</span></td></tr>")
            state.s = OUTPUT
        # Strict prompt match (maintains detailed rendering)
        elif (mm := prompt_regex.match(line)):
            color = prompt_colors[state.promptcount] if state.promptcount < len(prompt_colors) else "prot-manual-color"
            handle_promptmatch(color)
        # Lenient prompt line recognition (non-standard format containing @)
        elif '@' in line and not line.startswith('$'):
            state.promptcount += 1
            state.s = PROMPTSEEN
            color = prompt_colors[state.promptcount - 1] if state.promptcount - 1 < len(prompt_colors) else "prot-manual-color"
            promptindex = f"<span class='prot-counter {color}'>{state.promptcount}.</span>"
            result.append(f"<tr><td>{promptindex} {html.escape(line)}</td></tr>")
        # Output line
        elif state.s == OUTPUT:
            result.append(f"<tr><td><span class='vwr-output'>{html.escape(line)}</span></td></tr>")
        # Other lines (empty or unexpected)
        else:
            result.append(f"<tr><td>{html.escape(line)}</td></tr>")
    result.append("</table>\n\n")
    return "\n".join(result)


def render_prot_plain(student_content: str) -> str:
    """
    Render protocol file in plain format (for student view).
    Shows prompt numbers but NO colors, NO spec blocks (manual/extra/error).
    Similar to author course rendering but without colored indicators.
    """
    import sdrl.protocolchecker as protocolchecker
    import sdrl.programchecker as programchecker_mod

    @dataclasses.dataclass
    class State:
        s: int
        promptcount: int

    def handle_promptmatch():  # uses mm, result, state
        state.promptcount += 1
        state.s = PROMPTSEEN
        # show prompt number WITHOUT color
        promptindex = f"<span class='prot-counter'>{state.promptcount}.</span>"
        front = f"<span class='vwr-front'>{esc('front')}</span>"
        userhost = f"<span class='vwr-userhost'>{esc('userhost')}</span>"
        dir = f"<span class='vwr-dir'>{esc('dir')}</span>"
        time = f"<span class='vwr-time'>{esc('time')}</span>"
        num = f"<span class='vwr-num'> {esc('num')} </span>"
        back = f"<span class='vwr-back'>{esc('back')}</span>"
        result.append(f"<tr><td>{promptindex} {front} {userhost} {dir} {time} {num} {back}</td></tr>")

    def esc(groupname: str) -> str:  # abbrev; uses mm
        return html.escape(mm.group(groupname))

    extractor = protocolchecker.ProtocolExtractor()
    prompt_regex = extractor.prompt_regex
    result = ["\n<table class='vwr-table vwr-plain'>"]
    PROMPTSEEN, OUTPUT = (1, 2)
    state = State(s=OUTPUT, promptcount=0)
    # Filter out @PROT_SPEC and @TEST_SPEC annotations before rendering (students should not see them)
    content = protocolchecker.filter_prot_check_annotations(student_content)
    content = programchecker_mod.filter_program_check_annotations(content)
    for line in content.split('\n'):
        line = line.rstrip()  # get rid of newline
        mm = prompt_regex.match(line)
        if mm:
            handle_promptmatch()
        elif state.s == PROMPTSEEN:  # this is the command line
            # NO manual/extra/error blocks, just the command
            result.append(f"<tr><td><span class='vwr-cmd'>{html.escape(line)}</span></td></tr>")
            state.s = OUTPUT
        elif state.s == OUTPUT:
            result.append(f"<tr><td><span class='vwr-output'>{html.escape(line)}</span></td></tr>")
        else:
            assert False
    result.append("</table>\n\n")
    return '\n'.join(result)


def _load_author_prot_content(workdir: sdrl.participant.Student, prot_path: str) -> tuple[str | None, str | None]:
    """Load author .prot file content for comparison with student submission."""
    from sdrl.webapp.app import _gpg_available
    if not _gpg_available:
        return (None, None)
    import sdrl.protocolchecker as protocolchecker
    try:
        course = workdir.course
        if course:
            from sdrl.webapp.app import _get_builddir_from_context
            location_type, builddir = _get_builddir_from_context(course) or (None, None)
            if location_type is None:
                return (None, None)
            task_name = os.path.splitext(os.path.basename(prot_path))[0]
            encrypted_filename = f"{task_name}.prot.crypt"
            if location_type == 'local':
                # Local file path
                encrypted_path = os.path.join(builddir, encrypted_filename)
                if os.path.isfile(encrypted_path):
                    content = protocolchecker.load_encrypted_prot_file(encrypted_path)
                    if content:
                        return (content, f"{encrypted_path} (decrypted)")
            elif location_type == 'remote':
                # Remote HTTP(S) URL
                builddir_url = os.path.dirname(builddir)
                encrypted_url = f"{builddir_url}/{encrypted_filename}"
                try:
                    b.debug(f"Downloading encrypted prot file from {encrypted_url}")
                    response = requests.get(encrypted_url, timeout=10)
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix='.prot.crypt', delete=False) as tmp:
                        tmp.write(response.content)
                        tmp_path = tmp.name
                    try:
                        content = protocolchecker.load_encrypted_prot_file(tmp_path)
                        if content:
                            return content, f"{encrypted_url} (downloaded & decrypted)"
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except FileNotFoundError:
                            pass
                except requests.RequestException as e:
                    b.warning(f"Download failure: {e}")
    except (AttributeError, TypeError, OSError):
        pass
    return None, None
