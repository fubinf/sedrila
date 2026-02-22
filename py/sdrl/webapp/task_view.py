"""Task page: viewing files, diffs, and protocol renderings for a task."""
import html
import os
import pathlib
import subprocess
import traceback
import typing as tg

import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.constants as c
import sdrl.markdown as md
import sdrl.participant

from sdrl.webapp.resources import CSS, SEDRILA_UPDATE_URL
from sdrl.webapp.app import html_for_layout
from sdrl.webapp.prot_view import render_prot_compare, render_prot_plain, _load_author_prot_content


@bottle.route("/tasks/<taskname>/<path:path>")
@bottle.route("/tasks/<taskname>")
def serve_task(taskname: str, path: str | None = None):
    ctx = sdrl.participant.get_context()
    is_instructor = ctx.is_instructor

    raw_files = set()
    for s in ctx.studentlist:
        task = s.submissions.task(taskname)
        if task:
            raw_files.update(task.files)
    files = sorted(raw_files)

    files_bar = "".join(f"""
        <a href="/tasks/{taskname}{f}" class="file{" selected" if f == path else ""}">
            {pathlib.Path(f).name}
        </a>
    """ for f in files)

    if path:
        path = "/" + path
    elif len(files) > 0:
        path = files[0]

    def html_for_button(student_idx: int, state: str, task: sdrl.participant.SubmissionTask) -> str:
        return_file = f"<input type='hidden' name='return_file' value='{html.escape(path[1:])}'>" if path else None
        is_noncheck = task.state is None and state == c.SUBMISSION_NONCHECK_MARK
        return f"""
            <form class="action-button" action="{SEDRILA_UPDATE_URL}" method="POST"/>
                <input type="hidden" name="taskname" value="{html.escape(taskname)}"/>
                <input type="hidden" name="student_idx" value="{html.escape(str(student_idx))}"/>
                <input type="hidden" name="new_state" value="{html.escape(state)}"/>
                {return_file or ""}
                <label class="{"active" if task.state == state or is_noncheck else ""}">
                    {state}
                    <input type="submit"/>
                </label>
            </form>
        """

    buttons_markup = []
    for i, s in enumerate(ctx.studentlist):
        t = s.submissions.task(taskname)
        if t:
            is_check = t.is_student_checkable or (t.is_checkable and is_instructor)
            is_noncheck = t.is_student_checkable and not is_instructor
            buttons_markup.append(f"""
            <div class="student-buttons">
                <div>{s.student_gituser}</div>
                {html_for_button(i, c.SUBMISSION_CHECK_MARK, t) if is_check else ""}
                {html_for_button(i, c.SUBMISSION_NONCHECK_MARK, t) if is_noncheck else ""}
                {html_for_button(i, c.SUBMISSION_ACCEPT_MARK, t) if is_instructor and t.is_checkable else ""}
                {html_for_button(i, c.SUBMISSION_REJECT_MARK, t) if is_instructor and t.is_checkable else ""}
                {"REJECT_FINAL" if t.state == sdrl.participant.SubmissionTaskState.REJECT_FINAL else ""}
                {"ACCEPTED" if t.state == sdrl.participant.SubmissionTaskState.ACCEPT_PAST else ""}
            </div>
            """)
    buttons = "".join(buttons_markup)

    tasklink = html_for_tasklink(taskname, ctx.submission_find_taskname, ctx.course_url, ctx.is_instructor)

    try:
        file_markup = html_for_file(ctx.studentlist, path, ctx.is_instructor) if path else "no files"
    except Exception as ex:
        tb_lines = traceback.format_exception(type(ex), ex, ex.__traceback__)
        tb_text = ''.join(tb_lines)
        file_markup = f"<pre>{html.escape(tb_text)}</pre>"

    body = f"""
        <main id="task-main">
            <div id="files-bar">
                {files_bar}
            </div>
            <div id="code">
                <div id="file-path">
                    <div>{path if path else ""}</div>
                    <div>{tasklink}</div>
                </div>
                {file_markup}
                <div id="accept-buttons">
                    {buttons}
                </div>
            </div>
        </main>
    """
    return html_for_layout(taskname, body, selected=taskname)


def html_for_file(studentlist: list[sdrl.participant.Student], mypath, is_instructor: bool = False) -> str:
    """
    Page body showing each Workdir's version (if existing) of file mypath, and pairwise diffs where possible.
    We create this as a Markdown page, then render it.

    For .prot files:
    - If is_instructor=True: show comparison with author protocol (with colored indicators)
    - If is_instructor=False: show plain protocol rendering (student view)
    """
    SRC = 'src'
    BINARY = 'binary'
    MISSING = 'missing'
    binaryfile_suffixes = ('gif', 'ico', 'jpg', 'pdf', 'png', 'zip', 'sqlite', 'db')  # TODO 2: what else?
    suffix2lang = dict(  # see https://pygments.org/languages/  TODO 2: always just use the suffix?
        c="c", cc="c++", cpp="c++", cs="csharp",
        go="golang",
        h="c++", html="html",
        java="java", js="javascript",
        py="python",
        sh="shell",
        txt="")
    filename = os.path.basename(mypath)
    frontname, suffix = os.path.splitext(filename)

    def append_one_file(index):
        path = html.escape(workdir.path_actualpath(mypath))
        if not suffix or suffix[1:] in binaryfile_suffixes:
            lines.append(f"<a href='/raw/{index}/{path}'>{path}</a>")
            kinds.append(BINARY)
            return
        content = b.slurp(f"{workdir.topdir}{mypath}")
        if suffix == '.md':
            lines.append(content)
        elif suffix == '.prot':
            if is_instructor:
                # Instructor mode: try to show comparison with author protocol
                author_content, author_source = _load_author_prot_content(workdir, mypath)
                if author_content is not None:
                    # Author file exists: show comparison
                    lines.append(render_prot_compare(workdir.topdir, mypath, content, author_content, author_source))
                else:
                    # Fallback: no author file available, show plain student protocol
                    lines.append(render_prot_plain(content))
            else:
                # Student mode: show plain protocol rendering
                lines.append(render_prot_plain(content))
        else:  # any other suffix: assume this is a sourcefile
            language = suffix2lang.get(suffix[1:], "")
            if language == 'html':
                lines.append(f"<a href='/raw/{index}/{path}'>view as HTML page</a>")
            lines.append(f"```{language}")
            lines.append(content.rstrip("\n"))
            lines.append(f"```")
        kinds.append(SRC)

    def append_diff(index):
        prevdir = studentlist[index - 1]  # previous workdir
        toc.append(f"<a href='#diff-{html.escape(prevdir.topdir)}-{html.escape(workdir.topdir)}'>diff</a>  ")
        lines.append(f"<h2 id='diff-{html.escape(prevdir.topdir)}-{html.escape(workdir.topdir)}' {CSS}"
                     f">{index - 1}/{index}. diff {html.escape(prevdir.topdir)}/{html.escape(workdir.topdir)}</h2>")
        if kinds[-2:] != [SRC, SRC]:
            lines.append("No diff shown. It requires two source files, which we do not have here.")
            return
        diff_output = diff_files(prevdir.path_actualpath(mypath), workdir.path_actualpath(mypath))
        lines.append("\n```diff")
        lines.append(diff_output)
        lines.append("```")

    # ----- iterate through workdirs and prepare the sections:
    kinds = []  # which files are SRC, BINARY, or MISSING
    lines = []  # noqa, some entries will be entire file contents, not single lines
    toc = []
    for idx, workdir in enumerate(studentlist):
        toc.append(f"<a href='#{html.escape(workdir.topdir)}'>{idx}. {html.escape(workdir.topdir)}</a>  ")
        if not workdir.path_exists(mypath):
            lines.append(f"(('{html.escape(mypath)}' does not exist in '{html.escape(workdir.topdir)}'))")
            kinds.append(MISSING)
        else:
            append_one_file(idx)
        if idx % 2 == 1:
            append_diff(idx)
    # ----- render:
    the_toc, the_lines = '\n'.join(toc), '\n'.join(lines)
    the_html = md.render_plain_markdown(the_lines)
    return the_html


def html_for_tasklink(str_with_taskname: str, find_taskname_func: tg.Callable[[str], str],
                      course_url: str, is_instructor: bool) -> str:
    taskname = find_taskname_func(str_with_taskname)
    instructorpart = "instructor/" if is_instructor else ""
    return f"<a href='{html.escape(course_url)}{instructorpart}{html.escape(taskname)}.html'>task</a>" if taskname else ""


def diff_files(path1: str, path2: str) -> str:
    problem1 = b.problem_with_path(path1)
    problem2 = b.problem_with_path(path2)
    if problem1:
        return problem1
    if problem2:
        return problem2
    cmd = f"/usr/bin/diff '{path1}' '{path2}'"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "files are identical"
    elif result.returncode == 1:  # differences found
        return result.stdout
    else:  # there were execution problems
        return f"<p>('diff' exit status: {result.returncode}</p>\n{result.stderr}"
