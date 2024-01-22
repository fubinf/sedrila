# pytest tests
import argparse
import contextlib
import glob
import shutil
import zipfile

import bs4

import base as b
import sdrl.course
import sdrl.macros as macros
import sdrl.subcmd.author

expected_output = """[TERM::Concept 3]: Term 'Concept 3' is already defined
ch/glossary.md: These terms lack a definition: ['Concept 2 undefined', 'Concept 4 undefined']
wrote student files to  '../output'
wrote instructor files to  '../output/cino2r2s2tu'
ch/ch1/tg12/task113.duplicate: name collision: ch/ch1/tg11/task113.md and ch/ch1/tg12/task113.duplicate
"""

expected_filelist = [
    '_sedrila.yaml',
    'chapter-ch1.html', 'cino2r2s2tu', 'course.json',
    'favicon-32x32.png',
    'glossary.html',
    'index.html',
    'local.css',
    'myarchive.zip',
    'sedrila.css', 'sidebar.js',
    'task111r+a.html', 'task112.html', 'task113.html', 'tg11.html', 'tg12.html', 
]

expected_sidebar_task111 = """<div class="sidebar" id="sidebar">
    
<div class='indent0 no-stage'><a href='chapter-ch1.html' title="Chapter 1">ch1</a></div>
  <div class='indent1 no-stage'><a href='tg11.html' title="Task group 1.1">tg11</a></div>
    <div class='indent2 stage-alpha'><a href='task112.html' title="Task 1.1.2">task112</a> <span class='difficulty2' title='Difficulty: low'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 1.5 hours'>1.5</span><span class='assumed-by-decoration' title='assumed by: task111r+a'></span></div>
    <div class='indent2 stage-alpha'><a href='task113.html' title="Task 1.1.3">task113</a> <span class='difficulty3' title='Difficulty: medium'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 2.0 hours'>2.0</span><span class='required-by-decoration' title='required by: task111r+a'></span></div>
    <div class='indent2 stage-beta'><a href='task111r+a.html' title="Task 1.1.1 requires+assumes">task111r+a</a> <span class='difficulty1' title='Difficulty: verylow'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 1.0 hours'>1.0</span><span class='assumes-decoration' title='assumes: task112'></span><span class='requires-decoration' title='requires: task113'></span><span class='profiles-decoration'>PROFILE1</span></div>
  <div class="indent0 no-stage"><a href="glossary.html" title="glossary">Glossary of terms</a></div>
</div>
"""

expected_body_task111 = """
<div class="pagetype-task pagetype-task-difficulty1" id="taskbody">
 <div class="section section-background section-background-default">
  <h2 id="section_background">
   Section_Background
  </h2>
  <p>
   Section "Background" of Task 1.1.1.
Here, we mention
   <a class="glossary-termref-term" href="glossary.html#concept-3">
    Concept 3
    <span class="glossary-termref-suffix">
    </span>
   </a>
   ,
   <a class="glossary-termref-term" href="glossary.html#concept-3">
    ditto
    <span class="glossary-termref-suffix">
    </span>
   </a>
   ,
   <a class="glossary-termref-term" href="glossary.html#concept-3">
    Concept 3s
    <span class="glossary-termref-suffix">
    </span>
   </a>
   and also
   <a class="glossary-termref-term" href="glossary.html#concept-4-undefined">
    Concept 4 undefined
    <span class="glossary-termref-suffix">
    </span>
   </a>
   .
  </p>
  <div class="blockmacro blockmacro-warning">
   <strong>
    Warning:
   </strong>
   Body of Warning
  </div>
  <div class="blockmacro blockmacro-notice">
   <strong>
    Note:
   </strong>
   Body of Note
  </div>
  <details class="blockmacro blockmacro-hint">
   <summary>
    <strong>
     Hint:
    </strong>
    My Hint
   </summary>
   <p>
    Body of My Hint
   </p>
  </details>
 </div>
 <div class="blockmacro blockmacro-instructor">
  <h2 id="instructor-instructorpart-heading">
   Instructor Instructorpart Heading
  </h2>
  <p>
   Body of instructorpart
  </p>
 </div>
</div>
"""

def test_sedrila_author(capfd):
    """System test. Lots of hardcoded knowledge about the output of sedrila author."""
    # ----- prepare:
    shutil.rmtree("py/tests/output", ignore_errors=True)  # do our best to get rid of old outputs
    # ----- create output:
    with contextlib.chdir("py/tests/input"):
        _call_sedrila_author()
        actual_output = _get_output(capfd)
    # ----- check output:
    with contextlib.chdir("py/tests/output"):
        _check_filelist()
        _check_toc()
        _check_task_html()
        _check_zipfile()
        _check_glossary()
        _check_reporting(actual_output)


def _call_sedrila_author():
    # ----- prepare call:
    pargs = argparse.Namespace()
    pargs.config = b.CONFIG_FILENAME
    pargs.include_stage = "alpha"
    pargs.log = "WARNING"
    pargs.targetdir = "../output"
    # ----- do call akin to sdrl.subcmd.author.execute():
    b._testmode_reset()
    macros._testmode_reset()
    b.set_loglevel(pargs.log)
    course = sdrl.course.Course(pargs.config, read_contentfiles=True, include_stage=pargs.include_stage)
    sdrl.subcmd.author.generate(pargs, course)
    # ----- now force additional errors beyond what the test input produces:
    tg12 = course.taskgroup("tg12")
    task113duplicate = tg12._add_task(sdrl.course.Task().from_file("ch/ch1/tg12/task113.duplicate", taskgroup=tg12))
    # ----- check number of errors produced:
    assert b.num_errors == 2 + 1  # 2 from generate(), 1 additional


def _get_output(capfd) -> str:
    actual_output, actual_err = capfd.readouterr()
    capfd.close()  # stop capturing
    print(actual_output)  # so that sedrila output shows up in pytest output
    assert actual_err == ""
    return actual_output


def _check_filelist():
    actual_filelist = sorted(glob.glob('*'))
    assert actual_filelist == expected_filelist
    
def _check_toc():
    with open("task111r+a.html", encoding='utf8') as fp:
        actual_soup = bs4.BeautifulSoup(fp, features='html5lib', from_encoding='utf8')
        expected_soup = bs4.BeautifulSoup(expected_sidebar_task111, features='html5lib')
    actual_sidebar = str(actual_soup.find(id='sidebar'))
    expected_sidebar =  str(expected_soup.find(id='sidebar'))
    # _compare_line_by_line(actual_sidebar, expected_sidebar, strip=True, force_doublequotes=True)
    _compare_line_by_line(actual_sidebar, expected_sidebar, strip=True)


def _check_task_html():
    with open("task111r+a.html", encoding='utf8') as fp:
        actual_soup = bs4.BeautifulSoup(fp, features='html5lib', from_encoding='utf8')
        expected_soup = bs4.BeautifulSoup(expected_body_task111, features='html5lib')
    assert actual_soup.find('title').text == actual_soup.find('h1').text == "Task 1.1.1 requires+assumes"
    actual_body = actual_soup.find(id='taskbody')
    expected_body = expected_soup.find(id='taskbody')
    actual_html = actual_body.prettify()
    expected_html = expected_body.prettify()
    _compare_line_by_line(actual_html, expected_html)


def _check_glossary():
    pass  # will be tested by glossary_test.py


def _check_zipfile():
    with zipfile.ZipFile("myarchive.zip") as zip:
        assert zip.namelist() == ["ch1/myarchive/zipped.txt"]

def _check_reporting(actual_output: str):
    """Check actual_output line-for-line to be like expected_output."""
    _compare_line_by_line(actual_output, expected_output)


def _compare_line_by_line(actual: str, expected: str, strip=False):
    actual_lines = actual.split('\n')
    expected_lines = expected.split('\n')
    for i in range(len(actual_lines)):
        if strip:
            if actual_lines[i].strip() != expected_lines[i].strip():
                print("actual::", actual)
                assert actual_lines[i].strip() == expected_lines[i].strip()
        else:
            if actual_lines[i] != expected_lines[i]:
                print("actual::", actual)
                assert actual_lines[i] == expected_lines[i]
    assert len(actual_lines) == len(expected_lines)