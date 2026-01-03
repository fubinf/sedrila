"""Browse the virtual file system of a sdrl.participant.Context; see submissions and mark them."""
import base64
import getpass
import os
import pathlib
import subprocess
import tempfile
import traceback
import typing as tg
import html
import wsgiref.simple_server
import urllib.parse

import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.course
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
SEDRILA_UPDATE_URL = "/sedrila-update.action"
WORK_REPORT_URL = "/work.report"

# Global variable to store GPG passphrase for decrypting protocol files
gpg_passphrase: str | None = None

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


def _find_encrypted_prot_file(ctx: sdrl.participant.Context) -> str | None:
    """Find first encrypted protocol file in student work directories."""
    if hasattr(ctx, 'course') and ctx.course:
        course = ctx.course
        try:
            # course.context is the path/URL to course.json, which is in the builddir
            context_path = course.context
            # Only handle local file:// URLs or direct file paths
            # Cannot access encrypted files over HTTP(S)
            if context_path.startswith('http://') or context_path.startswith('https://'):
                return None
            if context_path.startswith('file://'):
                context_path = context_path[7:]  # remove 'file://' prefix
            builddir = os.path.dirname(context_path)
            if os.path.isdir(builddir):
                for filename in os.listdir(builddir):
                    if filename.endswith('.crypt'):
                        return os.path.join(builddir, filename)
        except (AttributeError, OSError, TypeError):
            pass
    return None


def _verify_gpg_passphrase(test_file: str, passphrase: str) -> bool:
    """Verify that passphrase can decrypt a test file."""
    import sdrl.protocolchecker as protocolchecker
    try:
        content = protocolchecker.load_encrypted_prot_file(test_file, passphrase=passphrase)
        return content is not None
    except Exception:
        return False


def run(ctx: sdrl.participant.Context):
    global gpg_passphrase
    # Make sure context is globally accessible for HTTP request handlers
    sdrl.participant._context = ctx
    # Only instructors need to decrypt protocol files
    if ctx.is_instructor:
        # Check if there are encrypted protocol files and ask for passphrase
        test_file = _find_encrypted_prot_file(ctx)
        if test_file:
            b.info("Encrypted protocol files found. Please enter GPG passphrase to decrypt them.")
            max_attempts = 3
            for attempt in range(max_attempts):
                passphrase = getpass.getpass("Enter GPG passphrase: ")
                if _verify_gpg_passphrase(test_file, passphrase):
                    gpg_passphrase = passphrase
                    b.info("Passphrase verified successfully. Starting webapp...")
                    break
                else:
                    remaining = max_attempts - attempt - 1
                    if remaining > 0:
                        b.warning(f"Incorrect passphrase. {remaining} attempt(s) remaining.")
                    else:
                        b.error("Failed to decrypt protocol files after maximum attempts. Starting webapp without decryption.")

    # Do not enable macros, because that makes the second start of webapp within one session crash
    # b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    # macroexpanders.register_macros(ctx.course)  # noqa
    b.info(f"Webserver starts. Visit 'http://localhost:{ctx.pargs.port}/'. Terminate with Ctrl-C.")

    class CustomHandler(wsgiref.simple_server.WSGIRequestHandler):
        timeout = 0.5  # half a second should always suffice for sending 'proper' requests

        def log_message(self, format, *args):
            pass

        def handle(self, *args, **kwargs):
            try:
                super().handle(*args, **kwargs)
            except TimeoutError:
                # timeouts are a regular thing because browsers open connections as stockpile
                # which our single-threaded server cannot handle concurrently.
                pass  # no need to do anything about them

    bottle.run(
        host='localhost', port=ctx.pargs.port, debug=DEBUG, reloader=False, quiet=True,
        handler_class=CustomHandler
    )


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
:root {
    --wa-blue: #004659;
    --wa-blue-90: #195869;
    --wa-blue-80: #336B7A;
    --wa-blue-70: #4C7D8A;
    --wa-blue-60: #66909B;
    --wa-blue-50: #7FA2AC;
    --wa-blue-40: #99B5BD;
    --wa-blue-30: #B2C7CD;
    --wa-blue-20: #CCDADE;
    --wa-blue-10: #E5ECEE;

    --wa-black-50: #808080;
    --wa-black-10: #E6E6E6;

    --wa-skyblue: #00A4D1;
    --wa-dark-olive: #58756A;
    --wa-light-olive: #86B0A0;
    --wa-orange: #E57050;
    --wa-deep-red: #813353;
}

li { padding: 0 !important; }

.scroll {
    overflow-y: auto;
}

#app {
    height: 100vh;
    width: 100vw;
    display: grid;
    grid-template-columns: 30ch 1fr;
    background-color: var(--wa-black-10);
}


#index-layout {
    display: grid;
    grid-template-columns: 1fr auto;
}

#content {
    overflow: auto;
}

main section {
    padding: 2rem;
}

.student-card {
    background-color: var(--wa-blue-90);
    padding: 0.5rem;
    color: var(--wa-black-10);
    margin: 0.2rem 0;
}

#task-select {
    overflow-y: auto;
    position: relative;
    color: var(--wa-black-10);
    background-color: var(--wa-blue-70);
}

#task-select a {
    text-decoration: none;
    color: inherit;
}

#task-select ul {
    margin: 0;
}

#home-link {
    position: sticky;
    display: block;
    top: 0;
    background-color: var(--wa-blue);
}

#task-select .item {
    /* border-top: 0.1rem solid var(--wa-blue); */
    padding: 0.5rem 1rem;
}

#files-bar {
    overflow-x: auto;
    position: sticky;
    top: 0;
    display: flex;
    gap: 0.2rem;
    background-color: var(--wa-blue);
}

#files-bar .file {
    padding: 0.5rem 1rem;
    background-color: var(--wa-blue-80);
}

#task-list {
    list-style: none;
    padding: 0;
}

#file-path {
    display: grid;
    grid-template-columns: 1fr auto;
}

#task-list li {
    display: grid;
    grid-template-columns: 1fr 2rem;
}

.task-indicator {
    display: grid;
    grid-template-columns: repeat(auto-fill, 1fr);
    gap: 0.1rem;
    padding: 0.1rem;
}

.indicator-bar.task-check { background-color: #00a2ff; }
.indicator-bar.task-unchecked { background-color: #ffb300; }
.indicator-bar.task-accept { background-color: #21db00; }
.indicator-bar.task-accept.past { background-color: #199e02; }
.indicator-bar.task-reject { background-color: #eb4034 }
.indicator-bar.task-reject.final { background-color: #b00c00 }

.legend-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem 1rem;
}
  
.legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
  
.legend-swatch {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border-radius: 0.2rem;
}

#code {
    padding: 1rem;
}

.task-link {
    display: block;
    background-color: var(--wa-blue-90);
}

.task-link.selected {
    background-color: var(--wa-blue-70);
}

a.file {
    text-decoration: none;
    color: var(--wa-blue-20);
}

.file.selected {
    background-color: var(--wa-blue-60);
}

.spacer-lg {
    height: 20rem;
}


#work-table {
    max-height: 80vh;
    overflow: auto;
}

#accept-buttons {
    position: fixed;
    bottom: 0;
    right: 0;
    padding: 1rem;
    margin: 1rem;
    background-color: var(--wa-black-10);
}

#task-main {
    display: grid;
    grid-template-rows: auto 1fr;
    text: black;
}

.student-buttons {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
    justify-content: end;
}

.action-button input[type="submit"] {
    display: none;
}

.action-button label {
    cursor: pointer;
    background-color: var(--wa-blue-50);
    padding: 0.5rem 1rem;
}

.action-button label.active {
    outline: 0.2rem solid var(--wa-blue-70);
}




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

/* Protocol comparison styles - new additions for error and hint blocks */
.prot-spec-error {
    background-color: #ffebee;
    border-left: 4px solid #eb4034;
    padding: 10px;
    margin: 10px 0;
}

.prot-spec-hint {
    background-color: #f0f8ff;
    border-left: 4px solid #4CAF50;
    padding: 10px;
    margin: 10px 0;
}

.prot-spec-hint details {
    cursor: pointer;
}

.prot-spec-hint summary {
    user-select: none;
    outline: none;
}

.prot-spec-hint summary:hover {
    text-decoration: underline;
}

/* Styling for code blocks in hint/error sections */
.prot-spec-code {
    background-color: #f5f5f5;
    padding: 10px;
    border-radius: 4px;
    max-height: 400px;
    overflow-y: auto;
}

/* Dark mode adjustments for protocol comparison styles */
@media (prefers-color-scheme: dark) {
    .prot-spec-error {
        background-color: #3c1f1f;
        border-left-color: #ff5555;
    }

    .prot-spec-hint {
        background-color: #1a2a3a;
        border-left-color: #66bb6a;
    }

    .prot-spec-code {
        background-color: #0a0a0a !important;
        color: #e0e0e0 !important;
    }

    .prot-spec-error .prot-spec-code {
        color: #ff9999 !important;
    }

    .prot-spec-hint pre,
    .prot-spec-error pre {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }

    .prot-spec-error pre {
        color: #ff9999;
    }

    /* Dark mode for accept-buttons panel */
    #accept-buttons {
        background-color: #1f1f1f;
    }

    .action-button label {
        background-color: var(--wa-blue-60);
    }

    .action-button label.active {
        outline-color: var(--wa-blue-80);
    }

    /* Dark mode for work report table alternating rows */
    tr.odd {
        background-color: #ddd;
        color: #000;
    }
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
def serve_index():
    ctx = sdrl.participant.get_context()
    body = f"""
        <main id="index-layout">
            <section class="scroll" id="work-report">
                <div class="legend-grid">
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-check"></span>
                    <span>CHECK</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-reject"></span>
                    <span>Rejected</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-accept"></span>
                    <span>Accepted</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-unchecked"></span>
                    <span>Not submitted</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-reject final"></span>
                    <span>Rejected (Final)</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-accept past"></span>
                    <span>Accepted (Past)</span>
                  </div>
                </div>
                <p>Select a task on the left, switch between its files at the top, select choice at bottom right.</p>  
                <h2>Work Report</h2>
                <p><b>w</b>: work time (from commit msgs), <b>v</b>: task time value</p>  
                {html_for_work_report_section(ctx)}
            </section>
            <section class="scroll" id="students-table">
                <h2>Student{"s" if len(ctx.studentlist) != 1 else ""}</h2>
                {html_for_student_table(ctx.studentlist)}
            </section>
        </main>
    """
    return html_for_layout("sedrila", body)

@bottle.route(SEDRILA_UPDATE_URL, method = "POST")
def serve_sedrila_update():
    """
    Update the state of a task in the sedrila webapp
    the json body of the post request should look like this:
        { taskname: str, student_idx: int, new_state: State }
    the response should look like this:
        { updated_state: State }
    """
    data = bottle.request.params
    ctx = sdrl.participant.get_context()
    idx = int(html.unescape(data.student_idx))
    student = ctx.studentlist[idx]
    taskname = html.unescape(data.taskname)
    new_state = data.new_state

    if not student.set_state(taskname, new_state):
        bottle.response.status = 404
        return f"invalid task ({taskname}) or state ({new_state})"

    if "return_file" in data:
        return bottle.redirect(f"/tasks/{taskname}/{html.unescape(data.return_file)}")
    elif not "no_redirect" in data:
        return bottle.redirect(f"/tasks/{taskname}")

    return { "updated_state": new_state }


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

@bottle.route("/raw/<student_idx>/<path:path>")
def serve_raw(student_idx: str, path: str):
    ctx = sdrl.participant.get_context()
    idx = int(student_idx)
    if idx >= len(ctx.studentlist):
        raise bottle.HTTPError(status=404, body="invalid student idx")
    student = ctx.studentlist[idx]
    return bottle.static_file(student.path_actualpath(f"/{path}"), root='.')

@bottle.route("/tasks/<taskname>/<path:path>")
@bottle.route("/tasks/<taskname>")
def serve_task(taskname: str, path: str | None = None):
    ctx = sdrl.participant.get_context()
    is_instructor = ctx.is_instructor

    raw_files = set()
    for s in ctx.studentlist:
        task = s.submissions.task(taskname)
        if task: raw_files.update(task.files)
    files = sorted(raw_files)

    files_bar = "".join(f"""
        <a href="/tasks/{taskname}{f}" class="file{" selected" if f == path else ""}">
            {pathlib.Path(f).name}
        </a>
    """ for f in files)

    if path: path = "/" + path
    elif len(files) > 0: path = files[0]

    def html_for_button(student_idx: int, state: str, task: sdrl.participant.SubmissionTask) -> str:
        return_file = f"<input type='hidden' name='return_file' value='{html.escape(path[1:])}'/>" if path else None
        return f"""
            <form class="action-button" action="{SEDRILA_UPDATE_URL}" method="POST"/>
                <input type="hidden" name="taskname" value="{html.escape(taskname)}"/>
                <input type="hidden" name="student_idx" value="{html.escape(str(student_idx))}"/>
                <input type="hidden" name="new_state" value="{html.escape(state)}"/>
                {return_file or ""}
                <label class="{"active" if task.state == state or (task.state == None and state == c.SUBMISSION_NONCHECK_MARK) else ""}">
                    {state}
                    <input type="submit"/>
                </label>
            </form>
        """

    buttons_markup = []
    for i, s in enumerate(ctx.studentlist):
        t = s.submissions.task(taskname)
        if t:
            buttons_markup.append(f"""
            <div class="student-buttons">
                <div>{s.student_gituser}</div>
                {html_for_button(i, c.SUBMISSION_CHECK_MARK, t) if t.is_student_checkable or (t.is_checkable and is_instructor) else ""}
                {html_for_button(i, c.SUBMISSION_NONCHECK_MARK, t) if t.is_student_checkable and not is_instructor else ""}
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

    def append_one_file(idx):
        path = html.escape(workdir.path_actualpath(mypath))
        if not suffix or suffix[1:] in binaryfile_suffixes:
            lines.append(f"<a href='/raw/{idx}/{path}'>{path}</a>")
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
                lines.append(f"<a href='/raw/{idx}/{path}'>view as HTML page</a>")
            lines.append(f"```{language}")
            lines.append(content.rstrip("\n"))
            lines.append(f"```")
        kinds.append(SRC)

    def append_diff():
        prevdir = studentlist[idx - 1]  # previous workdir
        toc.append(f"<a href='#diff-{html.escape(prevdir.topdir)}-{html.escape(workdir.topdir)}'>diff</a>  ")
        lines.append(f"<h2 id='diff-{html.escape(prevdir.topdir)}-{html.escape(workdir.topdir)}' {CSS}"
                     f">{idx - 1}/{idx}. diff {html.escape(prevdir.topdir)}/{html.escape(workdir.topdir)}</h2>")
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
        # lines.append(f"<h2 id='{html.escape(workdir.topdir)}' {CSS}>{idx}. {html.escape(workdir.topdir)}: {html.escape(filename)}</h2>")
        if not workdir.path_exists(mypath):
            lines.append(f"(('{html.escape(mypath)}' does not exist in '{html.escape(workdir.topdir)}'))")
            kinds.append(MISSING)
        else:
            append_one_file(idx)
        if idx % 2 == 1:
            append_diff()
    # ----- render:
    the_toc, the_lines = '\n'.join(toc), '\n'.join(lines)
    the_html = md.render_plain_markdown(the_lines)
    return the_html


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
    import sdrl.markdown as md
    import dataclasses

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
        return "\n<p style='color: red; background-color: #ffe6e6; padding: 10px;'><strong>⚠ Comparison not available:</strong> Author protocol file is encrypted and cannot be decrypted. Only instructors with the private key can view this comparison.</p>\n"
    def compare_results() -> list[protocolchecker.CheckResult]:
        # Always use temporary file approach since author content may be from encrypted source
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".prot", delete=False) as tmp:
                tmp.write(author_content or "")
                tmp.flush()
                tmp_path = tmp.name
            return checker.compare_files(student_file, tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    results = compare_results()
    def color_for(res: protocolchecker.CheckResult) -> str:
        rule = res.author_entry.check_rule if res.author_entry else None
        if rule and rule.skip:
            return "prot-skip-color"
        if res.requires_manual_check:
            return "prot-manual-color"
        if res.success:
            return "prot-ok-color"
        return "prot-alert-color"
    prompt_colors = [color_for(res) for res in results]
    result = ["\n<table class='vwr-table'>"]
    PROMPTSEEN, OUTPUT = (1, 2)
    state = State(s=OUTPUT, promptcount=0)
    # Filter out @PROT_SPEC annotations before rendering
    content = protocolchecker.filter_prot_check_annotations(student_content)
    for line in content.split('\n'):
        line = line.rstrip()
        mm = prompt_regex.match(line)
        if mm:
            # Get color for this prompt
            color = prompt_colors[state.promptcount] if state.promptcount < len(prompt_colors) else "prot-manual-color"
            handle_promptmatch(color)
        elif state.s == PROMPTSEEN:  # this is the command line
            idx = state.promptcount - 1
            # Show manual/extra/error blocks before the command
            if 0 <= idx < len(results):
                res = results[idx]
                rule = res.author_entry.check_rule if res.author_entry else None
                if rule and rule.manual_text:
                    result.append(f"<tr><td><div class='prot-spec-manual'>{md.render_plain_markdown(rule.manual_text)}</div></td></tr>")
                if rule and rule.text:
                    result.append(f"<tr><td><div class='prot-spec-manual'>{md.render_plain_markdown(rule.text)}</div></td></tr>")
                if rule and rule.extra_text:
                    result.append(f"<tr><td><div class='prot-spec-extra'>{md.render_plain_markdown(rule.extra_text)}</div></td></tr>")

                # Show error information and expected values
                if not res.success and res.error_message:
                    error_html = f"<div class='prot-spec-error'><pre>{html.escape(res.error_message)}</pre>"
                    # Even if there's an error message, try to show expected values if available
                    if res.author_entry:
                        error_html += f"<div class='prot-spec-hint' style='margin-top: 10px;'><strong>Expected command:</strong><br><code>{html.escape(res.author_entry.command)}</code>"
                        if res.author_entry.output:
                            author_output_escaped = html.escape(res.author_entry.output)
                            error_html += f"""<br><br><details>
<summary><strong>Expected output (click to expand)</strong></summary>
<pre class='prot-spec-code'>{author_output_escaped}</pre>
</details>"""
                        error_html += "</div>"
                    error_html += "</div>"
                    result.append(f"<tr><td>{error_html}</td></tr>")
                elif not res.success:
                    # Show command mismatch with expected value
                    if rule and rule.command_re and not res.command_match:
                        hint_html = f"<div class='prot-spec-error'>command_re did not match: <pre>{html.escape(rule.command_re)}</pre>"
                        if res.author_entry:
                            hint_html += f"<div class='prot-spec-hint' style='margin-top: 10px;'><strong>Standard command:</strong><br><code>{html.escape(res.author_entry.command)}</code></div>"
                        hint_html += "</div>"
                        result.append(f"<tr><td>{hint_html}</td></tr>")

                    # Show output mismatch with expected value in collapsible block
                    if rule and rule.output_re and not res.output_match:
                        hint_html = f"<div class='prot-spec-error'>output_re did not match: <pre>{html.escape(rule.output_re)}</pre>"
                        if res.author_entry:
                            author_output_escaped = html.escape(res.author_entry.output)
                            hint_html += f"""<div class='prot-spec-hint' style='margin-top: 10px;'>
<details>
<summary><strong>Standard output (click to expand)</strong></summary>
<pre class='prot-spec-code'>{author_output_escaped}</pre>
</details>
</div>"""
                        hint_html += "</div>"
                        result.append(f"<tr><td>{hint_html}</td></tr>")

                # For manual checks, show both command and output
                if res.requires_manual_check and res.author_entry:
                    hint_html = "<div class='prot-spec-hint'><strong>Reference for manual check:</strong><br><br>"
                    hint_html += f"<strong>Expected command:</strong><br><code>{html.escape(res.author_entry.command)}</code>"
                    if res.author_entry.output:
                        author_output_escaped = html.escape(res.author_entry.output)
                        hint_html += f"""<br><br><details>
<summary><strong>Expected output (click to expand)</strong></summary>
<pre class='prot-spec-code'>{author_output_escaped}</pre>
</details>"""
                    hint_html += "</div>"
                    result.append(f"<tr><td>{hint_html}</td></tr>")

            result.append(f"<tr><td><span class='vwr-cmd'>{html.escape(line)}</span></td></tr>")
            state.s = OUTPUT
        elif state.s == OUTPUT:
            result.append(f"<tr><td><span class='vwr-output'>{html.escape(line)}</span></td></tr>")
        else:
            assert False
    result.append("</table>\n\n")
    return "\n".join(result)


def render_prot_plain(student_content: str) -> str:
    """
    Render protocol file in plain format (for student view).
    Shows prompt numbers but NO colors, NO spec blocks (manual/extra/error).
    Similar to author course rendering but without colored indicators.
    """
    import sdrl.protocolchecker as protocolchecker
    import dataclasses

    @dataclasses.dataclass
    class State:
        s: int
        promptcount: int

    def handle_promptmatch():  # uses mm, result, state
        state.promptcount += 1
        state.s = PROMPTSEEN
        # Student view: show prompt number WITHOUT color
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
    result = ["\n<table class='vwr-table'>"]
    PROMPTSEEN, OUTPUT = (1, 2)
    state = State(s=OUTPUT, promptcount=0)
    # Filter out @PROT_SPEC annotations before rendering (students should not see them)
    content = protocolchecker.filter_prot_check_annotations(student_content)
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
    global gpg_passphrase
    import sdrl.protocolchecker as protocolchecker
    try:
        course = workdir.course
        if course and hasattr(course, 'context'):
            # course.context is the path/URL to course.json, which is in the builddir
            context_path = course.context
            # Only handle local file:// URLs or direct file paths
            # Cannot access encrypted files over HTTP(S)
            if context_path.startswith('http://') or context_path.startswith('https://'):
                return (None, None)
            if context_path.startswith('file://'):
                context_path = context_path[7:]  # remove 'file://' prefix
            # builddir is the directory containing course.json
            builddir = os.path.dirname(context_path)
            basename = os.path.basename(prot_path)
            encrypted_path = os.path.join(builddir, f"{basename}.crypt")
            if os.path.isfile(encrypted_path):
                content = protocolchecker.load_encrypted_prot_file(encrypted_path, passphrase=gpg_passphrase)
                if content:
                    return (content, f"{encrypted_path} (decrypted)")
    except (AttributeError, TypeError, OSError):
        pass
    return (None, None)


def html_for_page(title: str, course_url: str, body: str) -> str:
    return basepage_html.format(
        title=title,
        resources=html_for_resources(course_url),
        body=body,
        script=f"<script src='{WEBAPP_JS_URL}'></script>"
    )

def html_for_layout(title: str, content: str, selected: str | None = None) -> str:
    ctx = sdrl.participant.get_context()
    is_instructor = ctx.is_instructor

    # move relevant tasks up in list
    def checkable_first(name):
        for s in ctx.studentlist:
            t = s.submissions.task(name)
            if not t: continue

            # sort entries not marked for submission last for instructors
            if is_instructor and not t.is_registered: return (1, name)
            # sort checkable entries first
            if t and t.is_checkable: return (-1, name)
        return (0, name)
    tasks = sorted(ctx.tasknames, key=checkable_first)

    state_classes = dict([
        (None, "task-unchecked"),
        (sdrl.participant.SubmissionTaskState.CHECK, "task-check"),
        (sdrl.participant.SubmissionTaskState.ACCEPT, "task-accept"),
        (sdrl.participant.SubmissionTaskState.REJECT, "task-reject"),
        (sdrl.participant.SubmissionTaskState.REJECT_FINAL, "task-reject final"),
        (sdrl.participant.SubmissionTaskState.ACCEPT_PAST, "task-accept past"),
    ])

    def indicator_for_students(taskname: str) -> str:
        indicators = []
        for s in ctx.studentlist:
            t = s.submissions.task(taskname)
            indicators.append(f"""
            <div class="indicator-bar {state_classes[t.state] if t and t.state in state_classes else "unknown"}"></div>
            """)

        return f"""
            <div class="task-indicator">
                {"".join(indicators)}
            </div>
        """

    tasks_html = "".join(f"""
        <li>
            <a class="item task-link{' selected' if selected == t else ''}" href="/tasks/{t}">
                {t}
            </a>
            {indicator_for_students(t)}
        </li>

    """ for t in tasks)

    body = f"""
        <div id="app">
            <section id="task-select">
                <a class="item" id="home-link" href="/">Home</a>
                <ul id="task-list">
                    {tasks_html}
                </ul>
                <div class="spacer-lg"></div>
            </section>
            <section id="content">
                {content}
            </section>
        </div>
    """
    return html_for_page(title, ctx.course_url, body)

def html_for_resources(course_url: str) -> str:
    parsed = urllib.parse.urlparse(course_url)
    if parsed.scheme == "file":
        base = parsed.path.rstrip("/")
        def inline_css(name: str) -> str:
            path = os.path.join(base, name)
            try:
                css = b.slurp(path)
                return f"<style>\n{css}\n</style>"
            except Exception:
                return ""
        return (
            f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
            f"{inline_css('sedrila.css')}\n"
            f"{inline_css('local.css')}\n"
            f"{inline_css('codehilite.css')}\n"
            f'<link href="{WEBAPP_CSS_URL}" rel="stylesheet">\n'
        )
    return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
            f'<link href="{html.escape(course_url)}/sedrila.css" rel="stylesheet">\n'
            f'<link href="{html.escape(course_url)}/local.css" rel="stylesheet">\n'
            f'<link href="{html.escape(course_url)}/codehilite.css" rel="stylesheet">\n'
            f'<link href="{WEBAPP_CSS_URL}" rel="stylesheet">\n'
            )


def html_for_student_table(studentlist: list[sdrl.participant.Student]) -> str:
    tables = "".join(f"""
        <div class="student-card">
            <div class="student-name">
                {html.escape(s.student_name)} ({html.escape(s.student_id)})
            </div>
            <hr/>
            <div class="student-git">Git: {html.escape(s.student_gituser)}</div>
            <div class="partner-git">
                Partner: {html.escape(s.partner_gituser or "< none >")}
            </div>
        </div>
    """ for s in studentlist)

    return f"""
        <div>
            {tables}
        </div>
    """

def html_for_tasklink(str_with_taskname: str, find_taskname_func: tg.Callable[[str], str],
                      course_url: str, is_instructor: bool) -> str:
    taskname = find_taskname_func(str_with_taskname)
    instructorpart = "instructor/" if is_instructor else ""
    return f"<a href='{html.escape(course_url)}{instructorpart}{html.escape(taskname)}.html'>task</a>" if taskname else ""


def html_for_work_report_section(ctx: sdrl.participant.Context) -> str:
    if len(set(map(lambda s: s.student_gituser, ctx.studentlist))) != len(ctx.studentlist):
        b.warning("multiple students with same git username work report might be incorrect!")
    total_earned = { s.student_gituser: .0 for s in ctx.studentlist}
    total_work = { s.student_gituser: .0 for s in ctx.studentlist }

    def html_for_students(task: str) -> str:
        markup = []
        for s in ctx.studentlist:
            ct = s.course.task(task) # course_task
            if ct:
                total_earned[s.student_gituser] += ct.time_earned
                total_work[s.student_gituser] += ct.workhours

            markup.append(f"""
                <td>{round(ct.workhours, 2) if ct and ct.workhours else ""}</td>
                <td>{round(ct.time_earned, 2) if ct and ct.time_earned else ""}</td>
            """)

        return "".join(markup)

    tasks_markup = []
    sorted_tasks = sorted(ctx.tasknames)
    for i, name in enumerate(sorted_tasks):
        tasks_markup.append(f"""
            <tr class="{'even' if i % 2 == 0 else 'odd'}">
                <td>{name}</td>
                {html_for_students(name)}
            </tr>
        """)

    students_markup = []
    totals_markup = []
    for s in ctx.studentlist:
        students_markup.append(f"""
        <th colspan="2">{s.student_gituser}</th>
        """)
        totals_markup.append(f"""
        <td>{round(total_work[s.student_gituser], 2)}</td>
        <td>{round(total_earned[s.student_gituser], 2)}</td>
        """)

    return f"""
        <table id="work-table">
            <tr>
                <th></th>
                {''.join(students_markup)}
            </tr>
            <tr>
                <th>task</th>
                {f"<th>w</th><th>v</th>" * len(ctx.studentlist)}
            </tr>
            {''.join(tasks_markup)}
            <tr>
            <td>totals (worked, earned)</td>
            {''.join(totals_markup)}
            </tr>
        </table>
    """

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
