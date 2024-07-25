# pytest tests
import argparse
import contextlib
import glob
import os.path
import re
import shutil
import time
import zipfile

import bs4

import base as b
import cache
import sdrl.directory as dir
import sdrl.course as course
import sdrl.macros as macros
import sdrl.subcmd.author as author

INPUTDIR = "py/sdrl/tests/input"  # where test data is copied from
OUTPUTDIR = "py/sdrl/tests/output"  # where it and the test outputs go

expected_output1 = """../out/instructor/myarchive.zip
../out/myarchive.zip
../out/instructor/itree.zip
File 'ch/ch1/tg11/task111r+a.md':
   [TREEREF::/nonexisting.txt]: itreedir file 'itree.zip/nonexisting.txt' not found
../out/index.html
../out/instructor/index.html
../out/chapter-ch1.html
../out/instructor/chapter-ch1.html
../out/tg11.html
../out/instructor/tg11.html
../out/tg12.html
../out/instructor/tg12.html
../out/task111r+a.html
../out/instructor/task111r+a.html
../out/task112.html
../out/instructor/task112.html
../out/task113.html
../out/instructor/task113.html
../out/task121.html
../out/instructor/task121.html
../out/task122.html
../out/instructor/task122.html
File 'ch/glossary.md':
   [TERM::Concept 3]: Term 'Concept 3' is already defined
../out/glossary.html
../out/instructor/glossary.html
File 'ch/glossary.md':
   These terms lack a definition: ['Concept 2 undefined', 'Concept 4 undefined']
"""

expected_output2 = """File 'ch/ch1/tg11/task111r+a.md':
   [TREEREF::/nonexisting.txt]: itreedir file 'itree.zip/nonexisting.txt' not found
../out/task111r+a.html
../out/instructor/task111r+a.html
File 'ch/glossary.md':
   [TERM::Concept 3]: Term 'Concept 3' is already defined
../out/glossary.html
../out/instructor/glossary.html
File 'ch/glossary.md':
   These terms lack a definition: ['Concept 2 undefined', 'Concept 4 undefined']
"""

expected_output3 = """../out/instructor/itree.zip
../out/task111r+a.html
../out/instructor/task111r+a.html
../out/glossary.html
../out/instructor/glossary.html
"""

expected_output4 = """../out/index.html
../out/instructor/index.html
../out/tg12.html
../out/instructor/tg12.html
../out/task121.html
../out/instructor/task121.html
../out/task122.html
../out/instructor/task122.html
"""

expected_filelist1 = [
    'chapter-ch1.html', 'course.json',
    'favicon-32x32.png',
    'glossary.html',
    'index.html', 'instructor',
    'local.css',
    'myarchive.zip',
    'sedrila.css', 'sidebar.js',
    'task111r+a.html', 'task112.html', 'task113.html', 'task121.html', 'task122.html', 'tg11.html', 'tg12.html', 
]

expected_sidebar_task111 = """<div class="sidebar" id="sidebar">

  <div class="indent0 no-stage"><a href="chapter-ch1.html" title="Chapter 1">ch1</a></div>
    <div class="indent1 no-stage"><a href="tg11.html" title="Task group 1.1">tg11</a></div>
      <div class="indent2 stage-alpha"><a href="task112.html" title="Task 1.1.2">task112</a> <span class="difficulty2" title="Difficulty: low">⚫︎</span> <span class="timevalue-decoration" title="Timevalue: 1.5 hours">1.5</span><span class="assumed-by-decoration" title="assumed by: task111r+a"></span><!--tg11--></div>
      <div class="indent2 stage-alpha"><a href="task113.html" title="Task 1.1.3">task113</a> <span class="difficulty3" title="Difficulty: medium">⚫︎</span> <span class="timevalue-decoration" title="Timevalue: 2.0 hours">2.0</span><span class="required-by-decoration" title="required by: task111r+a"></span><!--tg11--></div>
      <div class="indent2 stage-beta"><a href="task111r+a.html" title="Task 1.1.1 requires+assumes">task111r+a</a> <span class="difficulty1" title="Difficulty: verylow">⚫︎</span> <span class="timevalue-decoration" title="Timevalue: 1.0 hours">1.0</span><span class="assumes-decoration" title="assumes: task112"></span><span class="requires-decoration" title="requires: task113"></span><!--tg11--></div>
    <div class="indent1 stage-alpha"><a href="tg12.html" title="Task group 1.2">tg12</a></div>
  <div class="indent0 no-stage"><a href="glossary.html">Glossary of terms</a></div>
  </div>
"""  # noqa

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
    <span class="treeref-prefix">
    </span>
    <span class="treeref">
     dummy.txt
    </span>
    <span class="treeref-suffix">
    </span>
    <span class="treeref-prefix">
    </span>
    <span class="treeref">
     ???
    </span>
    <span class="treeref-suffix">
    </span>
   </p>
  </details>
 </div>
</div>

"""


class Catcher:
    """Retrieve multiline stretches from captured output based on prominent textual block markers."""
    BEGIN = "########## %s ##########"
    END = "---------- %s END ----------"

    def __init__(self, capfd):
        self.capfd = capfd

    def print_begin(self, marker: str):
        print(self.BEGIN % marker)

    def print_end(self, marker: str):
        print(self.END % marker)

    def get_block(self, marker: str) -> str:
        """Return output from between the marker lines created by print_begin/print_end."""
        actual_output, actual_err = self.capfd.readouterr()
        assert actual_err == ""
        print(actual_output)  # make it available again
        regexp = f"{self.BEGIN % marker}\\n(.*){self.END % marker}"
        mm = re.search(regexp, actual_output, re.DOTALL)
        assert mm, f"marker '{marker}' not found"
        return mm.group(1)


def test_sedrila_author(capfd):
    """System test. Lots of hardcoded knowledge about the input and output of sedrila author."""
    # ----- prepare:
    shutil.rmtree(OUTPUTDIR, ignore_errors=True)  # do our best to get rid of old outputs
    os.mkdir(OUTPUTDIR)
    test_inputdir = os.path.join(OUTPUTDIR, "in")
    test_outputdir = os.path.join(OUTPUTDIR, "out")
    shutil.copytree(INPUTDIR, test_inputdir)  # test will modify the input data
    os.mkdir(test_outputdir)  # test outputs: sedrila-generated website
    catcher = Catcher(capfd)
    # ----- run tests:
    test_outputdir = os.path.join("..", "out")  # during the test, we are in test_inputdir
    with contextlib.chdir(test_inputdir):
        # --- step 1: create and check output as-is:
        course1, actual_output1 = call_sedrila_author("step 1: initial build", test_outputdir, catcher)
        check_output1(course1, actual_output1, expected_output1, errors=2)
        # --- step 2: build same config again:
        course2, actual_output2 = call_sedrila_author("step 2: identical rebuild", test_outputdir, catcher)
        check_output2(course2, actual_output2, expected_output2, errors=2)
        # --- step 3: repair errors:
        b.spit("ch/glossary.md", 
               b.slurp("ch/glossary.md").replace("[TERM0::Concept 3|Concept 3b]",
                                                 "[TERM0::Concept 3b|Concept 2 undefined|Concept 4 undefined]"))
        b.spit("itree.zip/nonexisting.txt", "now it exists!")
        course3, actual_output3 = call_sedrila_author("step 3: repair errors", test_outputdir, catcher)
        check_output2(course3, actual_output3, expected_output3)
        # --- step 4: modify 1 topmatter:
        b.spit("ch/ch1/tg12/task121.md", 
               b.slurp("ch/ch1/tg12/task121.md").replace("timevalue: 2.5",
                                                         "timevalue: 3.0"))
        course4, actual_output4 = call_sedrila_author("step 4: modify task121 topmatter", test_outputdir, catcher)
        check_output2(course4, actual_output4, expected_output4)
        # --- step 5: modify instructor includefile:
        # --- step 6: modify task body_i:
        # --- step 7: rename task:
        # --- step 8: add TERMREF:
        # --- step 9: add explains:


def call_sedrila_author(step: str, outputdir: str, catcher, start_clean=False) -> tuple[course.Coursebuilder, str]:
    pargs = argparse.Namespace()
    pargs.config = b.CONFIG_FILENAME
    pargs.clean = start_clean
    pargs.sums = False
    pargs.include_stage = "alpha"
    pargs.log = "INFO" if not step.startswith("step XXX") else "DEBUG"  # report built files
    pargs.targetdir = outputdir
    # ----- do call akin to sdrl.subcmd.author.execute():
    b._testmode_reset()  # noqa
    macros._testmode_reset()  # noqa
    b.set_loglevel(pargs.log)
    targetdir_s = pargs.targetdir
    targetdir_i = author._targetdir_i(pargs.targetdir)
    catcher.print_begin(step)
    author.prepare_directories(targetdir_s, targetdir_i)
    this_course = author.create_and_build_course(pargs, targetdir_i, targetdir_s)
    catcher.print_end(step)
    return this_course, catcher.get_block(step)


def check_output1(course: course.Coursebuilder, actual_output1: str, expected_output1: str, errors: int):
    with contextlib.chdir(course.targetdir_s):
        check_filelist(expected_filelist1)
        check_toc1()
        check_task_html1()
        check_zipfile1()
        check_glossary1()
        _compare_line_by_line(actual_output1, expected_output1)
        assert b.num_errors == errors  # see expected_output1: 2 errors, 1 warning


def check_output2(course: course.Coursebuilder, actual_output2: str, expected_output2: str, errors: int = 0):
    with contextlib.chdir(course.targetdir_s):
        check_filelist(expected_filelist1)  # should be as before
        _compare_line_by_line(actual_output2, expected_output2)
        assert b.num_errors == errors  # as before


def check_filelist(expected_filelist: list[str]):
    actual_filelist = sorted(glob.glob('*'))
    if actual_filelist != expected_filelist:
        print("expected:", expected_filelist)
        print("actual:  ", actual_filelist)
        assert False, "filelists do not match"
    assert os.path.exists('instructor/itree.zip')


def check_toc1():
    with open("task111r+a.html", encoding='utf8') as fp:
        actual_soup = bs4.BeautifulSoup(fp, features='html5lib', from_encoding='utf8')
        expected_soup = bs4.BeautifulSoup(expected_sidebar_task111, features='html5lib')
    actual_sidebar_task111_tag = str(actual_soup.find(id='sidebar'))
    expected_sidebar_task111_tag = str(expected_soup.find(id='sidebar'))
    # _compare_line_by_line(actual_sidebar, expected_sidebar, strip=True, force_doublequotes=True)
    _compare_line_by_line(actual_sidebar_task111_tag, expected_sidebar_task111_tag, strip=True)


def check_task_html1():
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
    if expected not in content:
        print(content)
        assert expected in content


def check_glossary1():
    pass  # will be tested by glossary_test.py


def check_zipfile1():
    with zipfile.ZipFile("myarchive.zip") as zipf:
        assert zipf.namelist() == ["myarchive/zipped.txt"]


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
