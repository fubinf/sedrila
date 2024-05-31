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

expected_output = """ch/ch1/tg12/task113.md: name collision: ch/ch1/tg11/task113.md and ch/ch1/tg12/task113.md
duplicate task: 'ch/ch1/tg12/task113.md'        'ch/ch1/tg11/task113.md'
[TERM::Concept 3]: Term 'Concept 3' is already defined
ch/glossary.md: These terms lack a definition: ['Concept 2 undefined', 'Concept 4 undefined']
wrote student files to  '../output'
wrote instructor files to  '../output/instructor'
"""

expected_filelist = [
    'chapter-ch1.html', 'course.json',
    'favicon-32x32.png',
    'glossary.html',
    'index.html', 'instructor',
    'local.css',
    'myarchive.zip',
    'sedrila.css', 'sedrila.yaml', 'sidebar.js',
    'task111r+a.html', 'task112.html', 'task113.html', 'task121.html', 'tg11.html', 'tg12.html', 
]

expected_sidebar_task111 = """<div class="sidebar" id="sidebar">
    
<div class='indent0 no-stage'><a href='chapter-ch1.html' title="Chapter 1">ch1</a></div>
  <div class='indent1 no-stage'><a href='tg11.html' title="Task group 1.1">tg11</a></div>
    <div class='indent2 stage-alpha'><a href='task112.html' title="Task 1.1.2">task112</a> <span class='difficulty2' title='Difficulty: low'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 1.5 hours'>1.5</span><span class='assumed-by-decoration' title='assumed by: task111r+a'></span></div>
    <div class='indent2 stage-alpha'><a href='task113.html' title="Task 1.1.3">task113</a> <span class='difficulty3' title='Difficulty: medium'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 2.0 hours'>2.0</span><span class='required-by-decoration' title='required by: task111r+a'></span></div>
    <div class='indent2 stage-beta'><a href='task111r+a.html' title="Task 1.1.1 requires+assumes">task111r+a</a> <span class='difficulty1' title='Difficulty: verylow'>&#x26ab;&#xfe0e;</span> <span class='timevalue-decoration' title='Timevalue: 1.0 hours'>1.0</span><span class='assumes-decoration' title='assumes: task112'></span><span class='requires-decoration' title='requires: task113'></span></div>
  <div class='indent1 stage-alpha'><a href='tg12.html' title="Task group 1.2">tg12</a></div>
  <div class="indent0 no-stage"><a href="glossary.html" title="glossary">Glossary of terms</a></div>
</div>
"""

expected_body_task111 = """
<div class="pagetype-task pagetype-task-difficulty1" id="taskbody">
 <div class="section section-background">
  <div class="section-subtypes section-background-subtypes">
   <div class="section-subtype section-background-default">
   </div>
  </div>
  <h2>
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
   <p>
    Body of Warning
   </p>
  </div>
  <div class="blockmacro blockmacro-notice">
   <strong>
    Note:
   </strong>
   <p>
    Enumeration:
    <span class="enumeration-ec">
     1
    </span>
    ,
    <span class="enumeration-ec">
     2
    </span>
    .
   </p>
  </div>
  <details class="blockmacro blockmacro-hint">
   <summary>
    <strong>
     Hint: My Hint
    </strong>
   </summary>
   <p>
    Body of My Hint
   </p>
  </details>
 </div>
</div>

"""


def test_includefile_path():
    with contextlib.chdir("py/tests/input"):
        # ----- prepare call:
        pargs = argparse.Namespace()
        pargs.cache = False
        pargs.config = b.CONFIG_FILENAME
        pargs.include_stage = "alpha"
        pargs.log = "WARNING"  # WARNING; for debugging, use INFO or DEBUG here
        pargs.targetdir = "../output"
        # ----- do call akin to start of sdrl.subcmd.author.execute():
        b._testmode_reset()
        macros._testmode_reset()
        b.set_loglevel(pargs.log)
        course = sdrl.subcmd.author.get_course(pargs)
        # ----- perform tests:
        def func(arg: str) -> str:
            call = macros.Macrocall(None, "ch/chapter/group/task.md", "task", 
                                    f"[INCLUDE::{arg}]", "INCLUDE", arg, None)
            return sdrl.subcmd.author.includefile_path(course, call)
        assert func("other") == "ch/chapter/group/other"
        assert func("/other2") == "ch/other2"
        assert func("ALT:other") == "altdir/chapter/group/other"
        assert func("ALT:/other2") == "altdir/other2"
        assert func("ALT:") == "altdir/chapter/group/task.md"


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
    pargs.cache = False
    pargs.config = b.CONFIG_FILENAME
    pargs.include_stage = "alpha"
    pargs.log = "WARNING"  # WARNING; for debugging, use INFO or DEBUG here
    pargs.targetdir = "../output"
    # ----- do call akin to sdrl.subcmd.author.execute():
    b._testmode_reset()
    macros._testmode_reset()
    b.set_loglevel(pargs.log)
    course = sdrl.subcmd.author.get_course(pargs)
    sdrl.subcmd.author.generate(course)
    # ----- check number of errors produced:
    assert b.num_errors == 4  # see expected_output


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
    actual_sidebar_task111_tag = str(actual_soup.find(id='sidebar'))
    expected_sidebar_task111_tag =  str(expected_soup.find(id='sidebar'))
    # _compare_line_by_line(actual_sidebar, expected_sidebar, strip=True, force_doublequotes=True)
    _compare_line_by_line(actual_sidebar_task111_tag, expected_sidebar_task111_tag, strip=True)


def _check_task_html():
    # ----- check the complex task111r+a:
    with open("task111r+a.html", encoding='utf8') as fp:
        actual_soup = bs4.BeautifulSoup(fp, features='html5lib', from_encoding='utf8')
        expected_soup = bs4.BeautifulSoup(expected_body_task111, features='html5lib')
    assert actual_soup.find('title').text == actual_soup.find('h1').text == "Task 1.1.1 requires+assumes"
    actual_body = actual_soup.find(id='taskbody')
    expected_body = expected_soup.find(id='taskbody')
    actual_html = actual_body.prettify()
    expected_html = expected_body.prettify()
    _compare_line_by_line(actual_html, expected_html)
    # ----- check resetting of enumerations in task112:
    with open("task112.html", encoding='utf8') as fp:
        content = fp.read()
    expected = "<span class='enumeration-ec'>1</span>"
    if not expected in content:
        print(content)
        assert expected in content


def _check_glossary():
    pass  # will be tested by glossary_test.py


def _check_zipfile():
    with zipfile.ZipFile("myarchive.zip") as zip:
        assert zip.namelist() == ["myarchive/zipped.txt"]

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
                assert (i+1, actual_lines[i].strip()) == (i+1, expected_lines[i].strip())
        else:
            if actual_lines[i] != expected_lines[i]:
                print("actual::", actual)
                assert (i+1, actual_lines[i]) == (i+1, expected_lines[i])
    assert len(actual_lines) == len(expected_lines)