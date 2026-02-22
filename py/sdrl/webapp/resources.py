"""Static resources and constants for the sedrila webapp."""
import importlib.resources

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
BONUS_REPORT_URL = "/bonus.report"

_files = importlib.resources.files("sdrl.webapp.files")
favicon32x32_png = (_files / "favicon-32x32.png").read_bytes()
basepage_html = (_files / "basepage.html").read_text(encoding="utf-8")
webapp_css = (_files / "webapp.css").read_text(encoding="utf-8")
webapp_js = (_files / "script.js").read_text(encoding="utf-8")
