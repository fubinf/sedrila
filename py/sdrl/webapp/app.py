"""Core webapp: run(), layout helpers, GPG setup, and common routes."""
import html
import json
import os
import tempfile
import urllib.parse

import bottle  # https://bottlepy.org/docs/dev/
import requests

import base as b
import sdrl.constants as c
import sdrl.participant

from sdrl.webapp.resources import (
    CSS, DEBUG, FAVICON_URL, WEBAPP_CSS_URL, WEBAPP_JS_URL,
    SEDRILA_REPLACE_URL, SEDRILA_UPDATE_URL,
    basepage_html, favicon32x32_png, webapp_css, webapp_js,
)

_gpg_available = False  # set to True after successful GPG priming


def _get_builddir_from_context(course) -> tuple[str, str] | None:
    """Extract builddir from course context."""
    if not hasattr(course, 'context'):
        return None
    context_path = course.context
    if context_path.startswith('file://'):
        local_path = context_path[7:]
        # If path points to a file (e.g., course.json), get its parent directory
        if os.path.isfile(local_path):
            local_path = os.path.dirname(local_path)
        return 'local', local_path
    elif context_path.startswith('http://') or context_path.startswith('https://'):
        return 'remote', context_path
    return None


def _find_encrypted_prot_file(ctx: sdrl.participant.Context) -> tuple[str, bool] | None:
    """Find first encrypted protocol file in student work directories or download from HTTP(S)."""
    if hasattr(ctx, 'course') and ctx.course:
        location_type, builddir = _get_builddir_from_context(ctx.course) or (None, None)
        if location_type == 'local':
            # Local file handling
            if os.path.isdir(builddir):
                for filename in os.listdir(builddir):
                    if filename.endswith('.crypt'):
                        return os.path.join(builddir, filename), False
        elif location_type == 'remote':
            # HTTP(S) URL handling, download first available encrypted file to temp
            builddir_url = os.path.dirname(builddir)
            try:
                # Fetch course.json to find available tasks
                course_json_url = f"{builddir_url}/course.json"
                response = requests.get(course_json_url, timeout=5)
                course_data = response.json()
                # Recursively find all 'name' values in course structure

                def find_names(data):
                    names = []
                    if isinstance(data, dict):
                        if 'name' in data and isinstance(data['name'], str):
                            names.append(data['name'])
                        for value in data.values():
                            names.extend(find_names(value))
                    elif isinstance(data, list):
                        for item in data:
                            names.extend(find_names(item))
                    return names
                # Try to download first available .prot.crypt file
                for task_name in find_names(course_data):
                    crypt_url = f"{builddir_url}/{task_name}.prot.crypt"
                    try:
                        crypt_response = requests.get(crypt_url, timeout=5)
                        if crypt_response.status_code == 200:
                            tmp_path = None
                            with tempfile.NamedTemporaryFile(suffix='.prot.crypt', delete=False) as tmp:
                                tmp.write(crypt_response.content)
                                tmp_path = tmp.name
                            return tmp_path, True
                    except requests.RequestException:
                        continue
            except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError):
                pass
    return None


def _prime_gpg_agent(test_file: str) -> bool:
    """Prime gpg-agent by attempting to decrypt a test protocol file.
    This triggers GPG to request the passphrase if needed,
    and gpg-agent caches it for the session.
    """
    import sdrl.protocolchecker as protocolchecker
    try:
        content = protocolchecker.load_encrypted_prot_file(test_file)
        return content is not None
    except RuntimeError as e:
        b.debug(f"Failed to prime GPG agent: {e}")
        return False


def _verify_gpg_keys(test_file: str) -> bool:
    """Verify that GPG private key exists and can decrypt a test file."""
    import sdrl.protocolchecker as protocolchecker
    try:
        content = protocolchecker.load_encrypted_prot_file(test_file)
        return content is not None
    except RuntimeError:
        return False


def run(ctx: sdrl.participant.Context):
    # Make sure context is globally accessible for HTTP request handlers
    sdrl.participant._context = ctx
    # Only instructors need to decrypt protocol files
    global _gpg_available
    if ctx.is_instructor:
        # Find an encrypted protocol file to prime gpg-agent with
        result = _find_encrypted_prot_file(ctx)
        if result:
            test_file, is_temp = result
            try:
                # Prime gpg-agent by attempting to decrypt (triggers passphrase prompt in shell)
                if _prime_gpg_agent(test_file):
                    _gpg_available = True
                else:
                    b.warning("GPG decryption failed. Protocol comparisons will not be available. "
                              "Check that gpg-agent is running and your private key is available.")
            finally:
                if is_temp:
                    try:
                        os.unlink(test_file)
                    except FileNotFoundError:
                        pass
        else:
            b.warning("No encrypted protocol files found. Protocol comparisons will not be available.")

    # Do not enable macros, because that makes the second start of webapp within one session crash
    # b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    # macroexpanders.register_macros(ctx.course)  # noqa
    b.info(f"Webserver starts. Visit 'http://localhost:{ctx.pargs.port}/'. Terminate with Ctrl-C.")

    # Import route modules so their @bottle.route decorators register.
    # Use importlib to avoid `import sdrl.webapp.*` shadowing the module-level `sdrl` binding.
    import importlib
    importlib.import_module('sdrl.webapp.task_view')
    importlib.import_module('sdrl.webapp.reports')

    # Use waitress as multi-threaded WSGI server to avoid browser connection
    # stockpile deadlocks (https://issues.chromium.org/issues/40978518)
    bottle.run(
        server='waitress',
        host='localhost',
        port=ctx.pargs.port,
        debug=DEBUG,
        reloader=False,
        quiet=True
    )


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


# ----- Common routes -----

@bottle.route(SEDRILA_UPDATE_URL, method="POST")
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
    elif "no_redirect" not in data:
        return bottle.redirect(f"/tasks/{taskname}")
    return {"updated_state": new_state}


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
