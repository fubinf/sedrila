"""Browse the virtual file system of a sdrl.participant.Context; see submissions and mark them."""
import base64
import os
import subprocess
import typing as tg

import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.constants as c
import sdrl.argparser
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant

meaning = """Specialized webserver for locally viewing contents of one or more student repo work directories."""
CSS = "class='viewer'"  # to be included in HTML tags
DEBUG = False  # TODO 1: turn off debug for release
DEFAULT_PORT = '8077'
FAVICON_URL = "/favicon-32x32.png"
VIEWER_CSS_URL = "/viewer.css"
VIEWER_JS_URL = "/script.js"
SEDRILA_REPLACE_URL = "/sedrila-replace.action"
favicon32x32_png_base64 = """iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAACqklEQVRYR+1Wv0t6cRQ9CiloQikk
RlpBU5BQDhlitTgouAoZDg0NmX9Is0MSQlMaItTSIIiDRBERgQ4OCuqgLUkikSD98Mu98Pp+Lc33
pOg7eEHkwefec965597Pk+3t7bXxiyEbEhgq8N8qMDMzA6PRiNfXV7y9vUEmk0Eul/M/xcXFBdrt
vwNkMBgwNzfHZymHgs7Tr1qtolQqdZ21nlMwMTEBvV4Pu90OjUbDyZVKBTc3NwxcKBQ6CIyPj4NI
jI2NcQ5FNptFsVjEw8MD7u/vpREQTi8vL2N9fZ0fCfTk5OTLrUGqeb1eNJtN7O/vv6vRK6nvHqC3
39nZYelbrRaCwSDL3CtWVlawurqKq6srpNPpviuuLwGqsLGxAZPJxMVisRjK5XLPwj6fj1txcHCA
RqPxPQTMZjOcTicXu729RTKZ7Fp4dHQUfr+fDRePx/uC0wFRCigUCgQCAYyMjODx8RGhUKjDgALS
0tISHA4HTk9Pkc/nv48AVXK73Zifn+eiR0dHPFofg1ql0+nYfF/55N88UQpQwuzsLDweD+fSKKZS
qQ58lUqF3d1dXF9fizKfkCyaAE0B9Zf63K0Ni4uLLH84HEa9Xhclv2gPCNXW1tZgtVq7toHkpzg+
PhYNLpmAVqvF9vb2pzao1WqW/+zsDLlc7ucIUOXNzU1MTU11tMFiscBms7H5Xl5efpbAwsICXC4X
g0QiEb4faPnc3d19MqYYJqJNKBSjXUByK5VKngZaTNSWw8ND1Go1MZgdZyQToGxyOy0dmoZMJoPp
6WlEo1HJ4JJNKCDQVb21tcWPz8/PSCQSks0neQ98fD3q++TkJJ6enng1Cx8hUmUYqAUEIlxQl5eX
OD8/l4r7fn5gAmRGuvvJiPTxMWgMTGBQwI95QwJDBX5dgT/hoVUQturVFQAAAABJRU5ErkJggg=="""
favicon32x32_png = base64.b64decode(favicon32x32_png_base64)
get_context = sdrl.participant.get_context  # abbreviation


def run(ctx: sdrl.participant.Context):
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    macroexpanders.register_macros(ctx.course)  # noqa
    b.info(f"Webserver starts. Visit 'http://localhost:{ctx.pargs.port}/'. Terminate with Ctrl-C.")
    bottle.run(host='localhost', port=ctx.pargs.port, debug=DEBUG, reloader=False)


basepage_html = """<!DOCTYPE html>
<html>
 <head>
  <title>{title}</title>
  <meta charset="utf-8">
  {resources}
 </head>
 <body class='viewer'>
  {body}
  {script}
 </body>
</html>
"""

viewer_css = """
h1.viewer, h2.viewer, h3.viewer {
  font-family: sans-serif;
  width: 100%;
  background-color: var(--main-color);
  padding: 0.5ex 1em;
  border-radius: 0.5ex;
  box-sizing: border-box;
}

td.viewer {
  padding: 0.3ex 1em;
}

tr.even {}

tr.odd {
    background-color: #ddd;
}

span.accept {
    background-color: #9c0;
}

span.reject {
    color: #eee;
    background-color: #c00;
}
"""

viewer_js = """
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
    body = "%s\n\n%s\n\n%s" % (
        html_for_submissionrelated_files(),
        html_for_remaining_submissions(),
        html_for_directorylist("/", breadcrumb=False),
    )
    return html_for_page("viewer", body)


@bottle.route(SEDRILA_REPLACE_URL, method="POST")
def serve_sedrila_replace():
    """
    On the HTML page, spots where the user can change the state are coded like so:
      <span id="mytaskname" data-index=0 class="sedrila-replace someclass">sometext</span> 
    When clicked, javascript will produce a POST request with a JSON body like so:
      { id: "mytaskname", index: 0, cssclass: "sedrila-replace someclass", text: "sometext" }
    This routine will respond with a JSON body like so:
      { class: "sedrila-replace1 newclass", text: "newtext" }
    and will call the state change function on the context.
    """
    data = bottle.request.json
    ctx = get_context()
    idx = data['index']
    student, taskname = ctx.studentlist[idx], data['id']
    taskstatus = student.submission[taskname]  # get task accept/reject status
    classes = set(data['cssclass'].split(' '))
    states = states_instructor = [c.SUBMISSION_CHECK_MARK, c.SUBMISSION_ACCEPT_MARK, c.SUBMISSION_REJECT_MARK]
    allclasses = set(states)
    newstatus = student.move_to_next_state(taskname, taskstatus)
    student.submission[taskname] = newstatus
    classes = (classes - allclasses)
    classes.add(newstatus)
    data['cssclass'] = ' '.join(classes)
    data['text'] = f"{idx}!" if newstatus == c.SUBMISSION_REJECT_MARK else f"{idx}"
    return data


@bottle.route(FAVICON_URL)
def serve_favicon():
    bottle.response.content_type = 'img/png'
    return favicon32x32_png


@bottle.route(VIEWER_CSS_URL)
def serve_css():
    bottle.response.content_type = 'text/css'
    return viewer_css


@bottle.route(VIEWER_JS_URL)
def serve_js():
    bottle.response.content_type = 'text/javascript'
    return viewer_js


@bottle.route("<mypath:path>/")
def serve_directory(mypath: str):
    title = f"D:{os.path.basename(mypath)}"
    body = html_for_directorylist(f"{mypath}/")
    return html_for_page(title, body)


@bottle.route("<mypath:path>")
def serve_vfile(mypath: str):
    if bottle.request.query.raw:  # ...?raw=workdirname
        return handle_rawfile(mypath, bottle.request.query.raw)
    title = f"F:{os.path.basename(mypath)}"
    body = html_for_file(f"{mypath}")
    return html_for_page(title, body)


def handle_rawfile(mypath: str, workdir: str):
    wd = get_context().students[workdir]
    return bottle.static_file(wd.path_actualpath(mypath), root='.')


def html_for_breadcrumb(path: str) -> str:
    parts = [f"<nav {CSS}><a href='/'>viewer</a>:"]
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


def html_for_resources(course_url: str) -> str:
    return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
            f'<link href="{course_url}/sedrila.css" rel="stylesheet">\n'
            f'<link href="{course_url}/local.css" rel="stylesheet">\n'
            f'<link href="{course_url}/codehilite.css" rel="stylesheet">\n'
            f'<link href="{VIEWER_CSS_URL}" rel="stylesheet">\n'
            )


def html_for_directorylist(mypath, breadcrumb=True) -> str:
    """A page listing the directories and files under mypath in the virtual filesystem."""
    dirs, files = get_context().ls(mypath)
    lines = [html_for_breadcrumb(mypath) if breadcrumb else ""]  # noqa
    lines.append(f"<h1 {CSS}>Contents of '{mypath}'</h1>")
    lines.append(f"<h2 {CSS}>Subdirectories</h2>")
    lines.append(f"<table {CSS}>")
    for idx, mydir in enumerate(sorted(dirs)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mydir}'>{mydir}</a></td>"
                     f"<td {CSS}>{html_for_tasklink(mydir)}</td>"
                     f"</tr>")
    lines.append("</table>")
    lines.append(f"<h2 {CSS}>Files</h2>")
    lines.append(f"<table {CSS}>")
    for idx, file in enumerate(sorted(files)):
        filepath = os.path.join(mypath, file)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{filepath}'>{file}</a></td>"
                     f"{html_for_file_existence(filepath)}"
                     f"<td {CSS}>{html_for_tasklink(filepath)}</td>"
                     f"</tr>")
    lines.append("</table>")
    body = "\n".join(lines)
    return body


def html_for_file(mypath) -> str:
    """
    Page body showing each Workdir's version (if existing) of file mypath, and pairwise diffs where possible.
    We create this as a Markdown page, then render it.
    """
    SRC = 'src'
    BINARY = 'binary'
    MISSING = 'missing'
    binaryfile_suffixes = ('pdf', 'zip')  # TODO 2: what else?
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
        content = b.slurp(f"{workdir.topdir}{mypath}")
        if suffix == '.md':
            lines.append(content)
        elif suffix == '.prot':
            lines.append(macroexpanders.prot_html(content))
        elif not suffix or suffix[1:] in binaryfile_suffixes:
            lines.append(f"<a href='?raw={workdir.topdir}'>{workdir.path_actualpath(mypath)}</a>")
            kinds.append(BINARY)
            return
        else:  # any other suffix: assume this is a sourcefile 
            language = suffix2lang.get(suffix[1:], "")
            if language == 'html':
                lines.append(f"<a href='?raw={workdir.topdir}'>view as HTML page</a>")
            lines.append(f"```{language}")
            lines.append(content.rstrip("\n"))
            lines.append(f"```")
        kinds.append(SRC)

    def append_diff():
        prevdir = get_context().studentlist[idx - 1]  # previous workdir
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
    for idx, workdir in enumerate(get_context().studentlist):
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
    macros.switch_part("viewer")
    mddict = md.render_markdown(mypath, filename, markdown, b.Mode.STUDENT, dict())
    return mddict['html']


def html_for_file_existence(mypath: str) -> str:
    """One or more table column entries with file existence markers for each file or file pair."""
    BEGIN = f'<td {CSS}>'
    END = '</td>'
    MISSING = '-- '
    entries = [BEGIN]
    context = sdrl.participant.get_context()
    for idx, wd in enumerate(context.studentlist):
        wd: sdrl.participant.Student  # type hint
        if wd.path_exists(mypath):
            taskname = wd.submission_find_taskname(mypath)
            if taskname:
                entries.append(f"<span id='{taskname}' data-index={idx} class='sedrila-replace'>{idx}</span>")
            else:
                entries.append(str(idx))
        else:
            entries.append(MISSING)
        entries.append(END)
        entries.append(BEGIN)
        if idx % 2 == 1:  # finish a pair
            if entries[-1] != MISSING and entries[-2] != MISSING:  # both files are present
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
                last = entries.pop()
                entries.append(f" {sign} ")
                entries.append(last)
            entries.append(END)
            entries.append(BEGIN)
        prev_wd = wd
    if entries[-1] == BEGIN:  # repair the end
        entries.pop()
    return ''.join(entries)


def html_for_page(title: str, body: str) -> str:
    return basepage_html.format(
        title=title,
        resources=html_for_resources(get_context().course_url),
        body=body,
        script=f"<script src='{VIEWER_JS_URL}'></script>"
    )


def html_for_remaining_submissions() -> str:
    def html_for_remainingness(subm: str) -> str:
        MISSING = '-- '
        parts = []
        for idx2, wd in enumerate(get_context().studentlist):
            parts.append(f"{str(idx2)} " if subm in wd.submissions_remaining else MISSING)
        return ''.join(parts)

    lines = [f"<h1 {CSS}>Submissions not covered above</h1>",
             f"<table {CSS}>"]
    for idx, submission in enumerate(sorted(get_context().submissions_remaining)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}>{submission}</td>"
                     f"<td {CSS}>{html_for_remainingness(submission)}</td>"
                     f"<td {CSS}>{html_for_tasklink(submission)}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_submissionrelated_files() -> str:
    lines = [f"<h1 {CSS}>Files with submission-related names</h1>",
             f"<table {CSS}>"]
    for idx, mypath in enumerate(sorted(get_context().submission_pathset)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mypath}'>{mypath}</a></td>"
                     f"{html_for_file_existence(mypath)}"
                     f"<td {CSS}>{html_for_tasklink(mypath)}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_tasklink(str_with_taskname: str) -> str:
    context = get_context()
    taskname = context.submission_find_taskname(str_with_taskname)
    instructorpart = "instructor/" if context.is_instructor else ""
    return f"<a href='{context.course_url}{instructorpart}{taskname}.html'>task</a>" if taskname else ""


def tr_tag(idx: int) -> str:
    color = "even" if idx % 2 == 0 else "odd"
    return f"<tr class='viewer {color}'>"


def diff_files(path1: str, path2: str) -> str:
    cmd = f"/usr/bin/diff '{path1}' '{path2}'"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "files are identical"
    elif result.returncode == 1:  # differences found
        return result.stdout
    else:  # there were execution problems
        return f"<p>('diff' exit status: {result.returncode}</p>\n{result.stderr}"
