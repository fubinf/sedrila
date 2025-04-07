"""Browse the virtual file system of a sdrl.participant.Context; see submissions and mark them."""
import base64
import os
import subprocess
import typing as tg

import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant

meaning = """Specialized webserver for locally viewing contents of one or more student repo work directories."""
CSS = "class='sview'"  # to be included in HTML tags
DEBUG = False  # turn off debug for release
DEFAULT_PORT = '8077'
FAVICON_URL = "/favicon-32x32.png"
WEBAPP_CSS_URL = "/webapp.css"
WEBAPP_JS_URL = "/script.js"
SEDRILA_REPLACE_URL = "/sedrila-replace.action"
WORK_REPORT_URL = "/work.report"
favicon32x32_png_base64 = """iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAE0ElEQVRYR8VXR0hdWxTdzxI1OrAG
K1ZQbDGoOFBEUOyiYsUKtmAdOPslIPzPR2fB2CAqqFgRLAiCJEKcKIgogi3YosFGdKCiEcvLXSf/
XN597z6/+RCz4Q3eOfusvc/a7VxFTU2NjpGR0W9KpbKciGyE32PIvmCk6evXr/8o6urq/hCM//0Y
VmVsvFLU1tbuPeLN1X04gAPKX3R7Zlbx+vVr5e3tLd3c3JAQiu+LCgXp6uqSnp4eYe/6+lrWxydP
npCVlRU7e3h4KKsDLENDQ6bDbWBNX1+fdHR0SPH582elnZ0dO3x3d8eM48dlcnKSZmdnZcHDw8Mp
ICCAATc0NNDV1ZWGHi5RXV0tYuKSHB9OK3p6epShoaHEneAIu7u7tLy8TJubm3R6eqoBDJCysjIy
MTFhexMTEzQ/Py/rqKenJ7148YLs7e3F/fPzcxofHyeWA8bGxvTy5UtGC5e+vj769OmT1vRwcHCg
rKwscX9vb4+6urq06iOkpaWlBFuQ7u5uEtj/7gAW4uLiyNvb+0HUQykyMpLdSlVaW1vp+PhYqxP5
+flkbW1Nqs6KDjg5OVFGRoZ4GLcHC3IC+svLy8XbcJ3p6WmamprS6kBVVRUJTU8SLtEBgFZUVNDT
p08ZABISiXV5eakB6OjoSJmZmRrryJWWlhaxmlQVLC0tqbCwkOE2NjbSxcUF25b0gaioKPLz8xPP
IUkWFxc1DHG99fV1srGxkTDR29tLOzs7GmeCgoIoLCyM5ZUqsxIH1MOwsbFBg4ODEjDULpgClaOj
o8yBwMBAUQcOw3F1yc3NJVtbW3r37h3Nzc2J2xIHAI7Y8jCgCb1580ZS387OzpSens6aE/ZMTU2p
oKBABEQvQOjQG7igVFGykObmZjo7O5N3AKvR0dH0/PlzUQG3XFlZEf/HxsaSj48Pra2t0fDwMFvn
2c2V1M+gWlA1BwcH1NHRISFHYxa4uLhQWlqaqATjAISglkE/WuvIyAitrq6ydX9/f4qIiBDPqIcO
jIE5VAgqRVU0HICRyspKMjAwYHqgFFQjHK6urpSamirSz2cEQobQIYQQ1UwHDvCA29bWRl++fLnf
AewmJCQQ2ieXgYEB2traovj4ePLy8pLQz3VSUlLIzc1NPMOTDTjAOzk5obdv30qM44/sOHZ3d6ek
pCRReWFhgd6/f89uggmoSj9XUj+zv79PnZ2dlJiYSB4eHjQzM0MfPnx4mAOYCehamGQQZC1ulJyc
rEE/R1TND77W3t5OOTk5zGnMCbRgddH6IFGnFLFDN0PigQE5UW9kMIjax+RramqS7ZBaHfD19aWY
mBgNOyg9lKCcYKTjxuqCMY1xLSdaHUBmo+RUHye8+Wh7IcFASUkJmZmZSWz19/fT9vb2jzkA7ezs
bMkj4j76OXpISAgFBweLxoSnNytjlOYPMQBlPkD4wfvo5zq4PVjgsrS0RGNjY7LGsXjvq9jCwoKK
iorY4YfQz63k5eWxIQUZGhqijx8//j8HcKq4uJjMzc3ZPOAtWSvavxt4qOLBioFUX1+v9VX9nwxA
4dmzZ6z3Hx0dEeL5EEH7BQN4oKAD3ie//sNEeJTiQ9H6ITf7CTrs0+xPAfivnwD+EMhXCnyeCzH+
XdDG5/ljMXEg2GrE5/k3AZpcXaA5fbgAAAAASUVORK5CYII="""
# created using https://favicon.io/favicon-generator/, Vollkorn 800, size 130
favicon32x32_png = base64.b64decode(favicon32x32_png_base64)


def run(ctx: sdrl.participant.Context):
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    macroexpanders.register_macros(ctx.course)  # noqa
    b.info(f"Webserver starts. Visit 'http://localhost:{ctx.pargs.port}/'. Terminate with Ctrl-C.")
    bottle.run(host='localhost', port=ctx.pargs.port, debug=DEBUG, reloader=False, quiet=True)


basepage_html = """<!DOCTYPE html>
<html>
 <head>
  <title>{title}</title>
  <meta charset="utf-8">
  {resources}
 </head>
 <body class='sview'>
  {body}
  {script}
 </body>
</html>
"""

webapp_css = """
h1.sview, h2.sview, h3.sview {
  font-family: sans-serif;
  width: 100%;
  background-color: var(--main-color);
  padding: 0.5ex 1em;
  border-radius: 0.5ex;
  box-sizing: border-box;
}

td.sview {
  padding: 0.3ex 1ex;
}

tr.even {}

tr.odd {
    background-color: #ddd;
}

span.NONCHECK, span.CHECK, span.ACCEPT, span.REJECT, span.REJECTOID {
    padding: 0.5ex;
    border-radius: 0.3ex;
}

span.CHECK {
    color: #111;
    background-color: #f7dc6f;
}

span.NONCHECK {
    color: #111;
    background-color: lightblue;
}

span.ACCEPT {
    background-color: #9c0;
}

span.REJECT {
    color: #eee;
    background-color: #c00;
}

span.REJECTOID {
    color: #111;
    background-color: orange;
}
"""

webapp_js = """
function sedrila_replace() {
    const span = this;
    const data = { 
      'id': span.id, 
      'index': parseInt(span.dataset.index), 
      'cssclass': span.className, 
      'text': span.textContent
    };

    fetch('%s', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
        .then(response => response.json())
        .then(json => {
            span.className = json.cssclass;
            span.textContent = json.text;
      })
      .catch(console.error);
};

document.querySelectorAll('.sedrila-replace').forEach(t => {
  t.addEventListener('click', sedrila_replace);
});
""" % SEDRILA_REPLACE_URL


@bottle.route("/")
def serve_root():
    ctx = sdrl.participant.get_context()
    body = "%s\n\n%s\n\n%s\n\n%s\n\n%s" % (
        html_for_instructions(ctx.is_instructor),
        html_for_student_table(ctx.studentlist),
        html_for_submissionrelated_files(ctx, ctx.submission_pathset),
        html_for_remaining_submissions(ctx, ctx.submissions_remaining),
        html_for_directorylist(ctx, "/", breadcrumb=False),
    )
    return html_for_page("sedrila", ctx.course_url, body)


@bottle.route(WORK_REPORT_URL)
def serve_work_report():
    ctx = sdrl.participant.get_context()
    return html_for_page("work report", ctx.course_url, html_for_work_report(ctx))


@bottle.route(SEDRILA_REPLACE_URL, method="POST")
def serve_sedrila_replace():
    """
    On the HTML page, spots where the user can change the state are coded like so:
      <span id="mytaskname" data-index=0 class="sedrila-replace someclass">sometext</span> 
    When clicked, javascript will produce a POST request with a JSON body like so:
      { id: "mytaskname", index: 0, cssclass: "sedrila-replace someclass", text: "sometext" }
    This routine will call the state change function on the context and respond with a JSON body like so:
      { cssclass: "sedrila-replace newclass", text: "newtext" }
    """
    data = bottle.request.json
    ctx = sdrl.participant.get_context()
    idx = data['index']
    student, taskname = ctx.studentlist[idx], data['id']
    taskstatus = student.submission[taskname]  # get task accept/reject status
    classes = set(data['cssclass'].split(' '))
    allclasses = set(student.possible_submission_states)
    newstatus = student.move_to_next_state(taskname, taskstatus)
    classes = (classes - allclasses)
    classes.add(newstatus)
    data['cssclass'] = ' '.join(classes)
    return data


@bottle.route(FAVICON_URL)
def serve_favicon():
    bottle.response.content_type = 'img/png'
    return favicon32x32_png


@bottle.route(WEBAPP_CSS_URL)
def serve_css():
    bottle.response.content_type = 'text/css'
    return webapp_css


@bottle.route(WEBAPP_JS_URL)
def serve_js():
    bottle.response.content_type = 'text/javascript'
    return webapp_js


@bottle.route("<mypath:path>/")
def serve_directory(mypath: str):
    title = f"D:{os.path.basename(mypath)}"
    context = sdrl.participant.get_context()
    body = html_for_directorylist(context, f"{mypath}/")
    return html_for_page(title, context.course_url, body)


@bottle.route("<mypath:path>")
def serve_vfile(mypath: str):
    context = sdrl.participant.get_context()
    if bottle.request.query.raw:  # ...?raw=workdirname
        student = context.students[bottle.request.query.raw]
        return handle_rawfile(student, mypath)
    title = f"F:{os.path.basename(mypath)}"
    body = html_for_file(context.studentlist, mypath)
    return html_for_page(title, context.course_url, body)


def handle_rawfile(student: sdrl.participant.Student, mypath: str):
    return bottle.static_file(student.path_actualpath(mypath), root='.')


def html_for_breadcrumb(path: str) -> str:
    parts = [f"<nav {CSS}><a href='/'>sedrila</a>:"]
    slashpos = path.find("/", 0)
    assert slashpos == 0
    nextslashpos = path.find("/", slashpos + 1)
    # ----- process path elements between slashes:
    while nextslashpos > 0:
        parts.append(f" / <a href='{path[:nextslashpos + 1]}'>{path[slashpos + 1:nextslashpos]}</a>")
        slashpos = nextslashpos
        nextslashpos = path.find("/", slashpos + 1)
    # ----- process last path element:
    if slashpos + 1 == len(path):
        parts.append(" /")  # dir path
    else:
        parts.append(f" / <a href='{path}'>{path[slashpos + 1:]}</a>")  # file path
    return f"{''.join(parts)}</nav>"


def html_for_directorylist(ctx: sdrl.participant.Context, mypath, breadcrumb=True) -> str:
    """A page listing the directories and files under mypath in the virtual filesystem."""
    dirs, files = ctx.ls(mypath)
    lines = [html_for_breadcrumb(mypath) if breadcrumb else ""]  # noqa
    lines.append(f"<h1 {CSS}>Contents of '{mypath}'</h1>")
    lines.append(f"<h2 id='subdirectories'{CSS}>Subdirectories</h2>")
    lines.append(f"<table {CSS}>")
    for idx, mydir in enumerate(sorted(dirs)):
        tasklink = html_for_tasklink(mydir, ctx.submission_find_taskname, ctx.course_url, ctx.is_instructor)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mydir}'>{mydir}</a></td>"
                     f"<td {CSS}>{tasklink}</td>"
                     f"</tr>")
    lines.append("</table>")
    lines.append(f"<h2 id='files' {CSS}>Files</h2>")
    lines.append(f"<table {CSS}>")
    for idx, file in enumerate(sorted(files)):
        filepath = os.path.join(mypath, file)
        tasklink = html_for_tasklink(filepath, ctx.submission_find_taskname, ctx.course_url, ctx.is_instructor)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{filepath}'>{file}</a></td>"
                     f"{html_for_file_existence(ctx.studentlist, filepath)}"
                     f"<td {CSS}>{tasklink}</td>"
                     f"</tr>")
    lines.append("</table>")
    body = "\n".join(lines)
    return body


def html_for_editable_cell(idx: int, student: sdrl.participant.Student, taskname: str) -> str:
    return (f"<span id='{taskname}' data-index={idx} "
            f"class='sedrila-replace {student.submission[taskname]}'>"
            f"{student.student_gituser}</span>")


def html_for_file(studentlist: list[sdrl.participant.Student], mypath) -> str:
    """
    Page body showing each Workdir's version (if existing) of file mypath, and pairwise diffs where possible.
    We create this as a Markdown page, then render it.
    """
    SRC = 'src'
    BINARY = 'binary'
    MISSING = 'missing'
    binaryfile_suffixes = ('gif', 'ico', 'jpg', 'pdf', 'png', 'zip')  # TODO 2: what else?
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

    def append_one_file():
        if not suffix or suffix[1:] in binaryfile_suffixes:
            lines.append(f"<a href='?raw={workdir.topdir}'>{workdir.path_actualpath(mypath)}</a>")
            kinds.append(BINARY)
            return
        content = b.slurp(f"{workdir.topdir}{mypath}")
        if suffix == '.md':
            lines.append(content)
        elif suffix == '.prot':
            lines.append(macroexpanders.prot_html(content))
        else:  # any other suffix: assume this is a sourcefile 
            language = suffix2lang.get(suffix[1:], "")
            if language == 'html':
                lines.append(f"<a href='?raw={workdir.topdir}'>view as HTML page</a>")
            lines.append(f"```{language}")
            lines.append(content.rstrip("\n"))
            lines.append(f"```")
        kinds.append(SRC)

    def append_diff():
        prevdir = studentlist[idx - 1]  # previous workdir
        toc.append(f"<a href='#diff-{prevdir.topdir}-{workdir.topdir}'>diff</a>  ")
        lines.append(f"<h2 id='diff-{prevdir.topdir}-{workdir.topdir}' {CSS}"
                     f">{idx - 1}/{idx}. diff {prevdir.topdir}/{workdir.topdir}</h2>")
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
        toc.append(f"<a href='#{workdir.topdir}'>{idx}. {workdir.topdir}</a>  ")
        lines.append(f"<h2 id='{workdir.topdir}' {CSS}>{idx}. {workdir.topdir}: {filename}</h2>")
        if not workdir.path_exists(mypath):
            lines.append(f"(('{mypath}' does not exist in '{workdir.topdir}'))")
            kinds.append(MISSING)
        else:
            append_one_file()
        if idx % 2 == 1:
            append_diff()
    # ----- render:
    the_toc, the_lines = '\n'.join(toc), '\n'.join(lines)
    markdown = (f"{html_for_breadcrumb(mypath)}\n"
                f"<h1 {CSS}>{mypath}</h1>\n"
                f"{the_toc}\n"
                f"{the_lines}")
    macros.switch_part("webapp")
    mddict = md.render_markdown(mypath, filename, markdown, b.Mode.STUDENT, dict())
    return mddict['html']


def html_for_file_existence(studentlist: list[sdrl.participant.Student], mypath: str) -> str:
    """One or more table column entries with file existence markers for each file or file pair."""
    def file_exists_at(idx: int) -> bool:
        return studentlist[idx].path_exists(mypath)
    
    BEGIN = f'<td {CSS}>'
    END = '</td>'
    MISSING = '-- '
    entries = []
    for idx, wd in enumerate(studentlist):
        wd: sdrl.participant.Student  # type hint
        if wd.path_exists(mypath):
            taskname = wd.submission_find_taskname(mypath)
            if taskname:
                entries.append(f"{BEGIN}{html_for_editable_cell(idx, wd, taskname)}{END}")
            else:
                entries.append(f"{BEGIN}{wd.student_gituser}{END}")
        else:
            entries.append(f"{BEGIN}{MISSING}{END}")
        if idx % 2 == 1:  # finish a pair
            if file_exists_at(idx) and file_exists_at(idx-1):
                size_even, size_odd = prev_wd.path_actualsize(mypath), wd.path_actualsize(mypath)  # noqa
                if size_even > 1.5 * size_odd:
                    sign = ">>"
                elif size_even > size_odd:
                    sign = ">"
                elif size_even == size_odd:
                    sign = "="
                elif 1.5 * size_even < size_odd:
                    sign = "<<"
                elif size_even < size_odd:
                    sign = "<"
                else:
                    assert False
            else:
                sign = ""
            last = entries.pop()
            entries.append(f"{BEGIN}{sign}{END}")
            entries.append(last)
        prev_wd = wd
    return ''.join(entries)


def html_for_instructions(is_instructor: bool):
    """Explain how to use interactively what html_for_editable_cell() generates."""
    result = [
        "<ul>",
        " <li>Browse <a href='#subdirectories'>directories</a>, "
        "<a href='#files'>files</a>, "
        "<a href='#submissions'>submitted tasks</a>, "
        "<a href='#submissionrelated'>submission-related files</a>, or "
        f"the <a href='{WORK_REPORT_URL}'>work report</a> "
        "of one or more student file trees.</li>",
        " <li>Cycle through the following states by clicking the colored cells "
        f"for existing entries of '{c.SUBMISSION_FILE}':<br>"]
    if is_instructor:
        states = [("Please check", c.SUBMISSION_CHECK_MARK),
                  ("Accepted", c.SUBMISSION_ACCEPT_MARK),
                  ("Rejected", c.SUBMISSION_REJECT_MARK), ]
    else:
        states = [("Submit", c.SUBMISSION_CHECK_MARK),
                  ("Do not submit", c.SUBMISSION_NONCHECK_MARK), ]
    explanations = [f"<span class='{state}'>{text}</span>" for text, state in states]
    result.append(', '.join(explanations))
    result.append("</li></ul>")
    return '\n'.join(result)


def html_for_page(title: str, course_url: str, body: str) -> str:
    return basepage_html.format(
        title=title,
        resources=html_for_resources(course_url),
        body=body,
        script=f"<script src='{WEBAPP_JS_URL}'></script>"
    )


def html_for_remaining_submissions(ctx: sdrl.participant.Context, submissions_remaining: set[str]) -> str:
    def html_for_remainingness(subm: str) -> str:
        MISSING = '-- '
        parts = []
        for idx2, wd in enumerate(ctx.studentlist):
            parts.append("<td {CSS}>")
            parts.append(f"{html_for_editable_cell(idx2, wd, subm)} " if subm in wd.submissions_remaining else MISSING)
            parts.append("</td>")
        return ''.join(parts)

    lines = [f"<h1 id='submissions' {CSS}>Submissions not covered above</h1>",
             f"<table {CSS}>"]
    for idx, submission in enumerate(sorted(submissions_remaining)):
        tasklink = html_for_tasklink(submission, ctx.submission_find_taskname, ctx.course_url, ctx.is_instructor)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}>{submission}</td>"
                     f"<td {CSS}>{html_for_remainingness(submission)}</td>"
                     f"<td {CSS}>{tasklink}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_resources(course_url: str) -> str:
    return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
            f'<link href="{course_url}/sedrila.css" rel="stylesheet">\n'
            f'<link href="{course_url}/local.css" rel="stylesheet">\n'
            f'<link href="{course_url}/codehilite.css" rel="stylesheet">\n'
            f'<link href="{WEBAPP_CSS_URL}" rel="stylesheet">\n'
            )


def html_for_student_table(studentlist: list[sdrl.participant.Student]) -> str:
    lines = [f"<table {CSS}>"]
    lines.append(f"{tr_tag(-1)}<td {CSS}><b>student_name</b></td><td {CSS}><b>student_id</b></td>"
                 f"<td {CSS}><b>student_gituser</b></td><td {CSS}><b>partner_gituser</b></td>")
    for idx, stud in enumerate(studentlist):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}>{stud.student_name}</td>"
                     f"<td {CSS}>{stud.student_id}</td>"
                     f"<td {CSS}>{stud.student_gituser}</td>"
                     f"<td {CSS}>{stud.partner_gituser or '--'}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_submissionrelated_files(ctx: sdrl.participant.Context, submission_pathset: set[str]) -> str:
    lines = [f"<h1 id='submissionrelated' {CSS}>Files with submission-related names</h1>",
             f"<table {CSS}>"]
    for idx, mypath in enumerate(sorted(submission_pathset)):
        tasklink = html_for_tasklink(mypath, ctx.submission_find_taskname, ctx.course_url, ctx.is_instructor)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mypath}'>{mypath}</a></td>"
                     f"{html_for_file_existence(ctx.studentlist, mypath)}"
                     f"<td {CSS}>{tasklink}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_tasklink(str_with_taskname: str, find_taskname_func: tg.Callable[[str], str],
                      course_url: str, is_instructor: bool) -> str:
    taskname = find_taskname_func(str_with_taskname)
    instructorpart = "instructor/" if is_instructor else ""
    return f"<a href='{course_url}{instructorpart}{taskname}.html'>task</a>" if taskname else ""


def html_for_work_report(ctx: sdrl.participant.Context) -> str:
    tasks = [(task.path, task.name) for task in ctx.course.taskdict.values()]
    elems = [f"<h1 {CSS}>Tasks with time worked (w) or earned (e)</h1>\n",
             f"<p>Colors for time earned: ",
             f"<span class='{c.SUBMISSION_ACCEPT_MARK}'>Accepted</span>, "
             f"<span class='{c.SUBMISSION_REJECTOID_MARK}'>Rejected (resubmittable)</span>, "
             f"<span class='{c.SUBMISSION_REJECT_MARK}'>Rejected (final)</span>"
             f"</p>\n",
             f"<table {CSS}>\n",
             f"<thead {CSS}>\n",
             "<tr {CSS}>",
             f"<th></th>",
             ''.join((f"<th colspan=2>{s.student_gituser}</th>" for s in ctx.studentlist)),
             f"</tr>",
             "<tr {CSS}>",
             f"<th>Task</th>",
             ''.join(("<th>w</th><th>e</th>" for _ in ctx.studentlist)),
             f"</tr>",
             f"</thead>\n"]
    idx = 0
    for taskpath, taskname in sorted(tasks):
        # ----- make sure this task belongs into the report:
        workhours = [s.course.task(taskname).workhours for s in ctx.studentlist]
        states = [s.course.task(taskname).acceptance_state for s in ctx.studentlist]
        is_relevant = sum(workhours) > 0.0 or any((s != c.SUBMISSION_NONCHECK_MARK for s in states))
        if not is_relevant:
            continue  # nothing interesting would be in this row
        # ----- produce general part of row:
        idx += 1
        elems.append(tr_tag(idx))
        elems.append(f"<td {CSS}>{taskpath}</td>")
        # ----- produce student-specific parts of row:
        for stud in ctx.studentlist:
            task = stud.course.task(taskname)
            elems.append(f"<td {CSS}>{round(task.workhours, 2) if task.workhours else ''}</td>")
            if task.acceptance_state != c.SUBMISSION_NONCHECK_MARK:
                time_earned = round(task.time_earned, 2)
                elems.append(f"<td {CSS}><span class='{task.acceptance_state}'>{time_earned}</span></td>")
            else:
                elems.append(f"<td {CSS}></td>")
        elems.append("</tr>\n")
    elems.append(f"<thead {CSS}>")
    elems.append("<tr>")
    elems.append("<th>Total:</th>")
    for stud in ctx.studentlist:
        workhours_total = sum([t.workhours for t in stud.course.taskdict.values()])
        time_earned_total = sum([t.time_earned for t in stud.course.taskdict.values()])
        elems.append(f"<th>{round(workhours_total, 2)}</th><th>{round(time_earned_total, 2)}</th>")
    elems.append("</tr>")
    elems.append("</thead>")
    elems.append("</table>\n")
    return ''.join(elems)


def tr_tag(idx: int) -> str:
    color = "even" if idx % 2 == 0 else "odd"
    return f"<tr class='sview {color}'>"


def diff_files(path1: str, path2: str) -> str:
    cmd = f"/usr/bin/diff '{path1}' '{path2}'"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "files are identical"
    elif result.returncode == 1:  # differences found
        return result.stdout
    else:  # there were execution problems
        return f"<p>('diff' exit status: {result.returncode}</p>\n{result.stderr}"
