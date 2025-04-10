"""
Created by ChatGPT today as a response to the following prompt:

-----
Forget the past context.
Using Python, we will be renaming files and rewriting file content in three corresponding directory trees chapterdir, altdir and itreedir.

chapterdir looks for instance as follows:

./Basis/IDE/IDE-First-Steps.md
./Basis/IDE/IDE-Linux.md
./Basis/IDE/IDE-macOS.md
./Basis/IDE/IDE-Windows.md
./Basis/IDE/index.md
./Basis/IDE/VSNoticeCodium.inc
./Basis/IDE/VSSetup.inc
./Basis/index.md
./Basis/Repo/Einreichungen.md
./Basis/Repo/Git101.md
./Basis/Repo/index.md
./Basis/Repo/Kommandoprotokolle.md
./Basis/Repo/Markdown.md
./Basis/Repo/Sedrila-einrichten.md
./Basis/Repo/Shellprompt.md
./Basis/Repo/Zeiterfassung.md
./Basis/Schluss/index.md
./Basis/Schluss/requires-assumes.md
./Basis/Schluss/Schwierigkeitsstufen.md
./Basis/Schluss/Themenauswahl.md
./Basis/Unix-Umgebung/Abgabe.inc
./Basis/Unix-Umgebung/CdLsMvEtc.inc
./Basis/Unix-Umgebung/CheckPython.inc
./Basis/Unix-Umgebung/CLI-Linux-apt.md
./Basis/Unix-Umgebung/CLI-MacOS-brew.md
./Basis/Unix-Umgebung/CLI-Windows-WSL.md
./Basis/Unix-Umgebung/index.md
./Basis/Unix-Umgebung/InstructorCheckLinux.inc
./glossary.md
./index.md
./Sprachen/C/C_CheckCompile.inc
./Sprachen/C/C_CompilerAssemblerLinker.md
./Sprachen/C/C_IDELinux.md
./Sprachen/C/C_IDEmacOS.md
./Sprachen/C/C_IDEWindows.md
./Sprachen/C/C_InstructorCheck.inc
./Sprachen/C/C_Preprocessor.md
./Sprachen/C/C_ToolchainLinuxApt.md
./Sprachen/C/C_ToolchainMacOSBrew.md
./Sprachen/C/C_ToolchainWindowsWSL.md
./Sprachen/C/C_VSBuildScript.inc
./Sprachen/C/C_VSNoticeCodium.inc
./Sprachen/C/C_VSSetup.inc
./Sprachen/C/index.md
./Sprachen/Go/cog-pin.md
./Sprachen/Go/go-file-system.md
./Sprachen/Go/go-http-chat-core.md
./Sprachen/Go/go-http-chat-database.md
./Sprachen/Go/go-http-chat-security.md
./Sprachen/Go/index.md
./Sprachen/Go0/go-basics-i.md
./Sprachen/Go0/go-basics-ii.md
./Sprachen/Go0/go-ide.md
./Sprachen/Go0/go-interfaces.md
./Sprachen/Go0/index.md
./Sprachen/Go0/snippets/go-basics-converter.go
./Sprachen/Go0/snippets/go-basics-grades.py
./Sprachen/Go0/snippets/go-basics-validator.go
./Sprachen/Go0/snippets/hello_world.go
./Sprachen/index.md
./Sprachen/Python/index.md
./Sprachen/Python/PEP8.md
./Sprachen/Python/py-Context-Managers.md
./Sprachen/Python/py-Function-Arguments-Advanced.md
./Sprachen/Python/py-Function-Arguments-Basic.md
./Sprachen/Python/py-Funktionale-Programmierung.md
./Sprachen/Python/py-Import.md
./Sprachen/Python/py-Iterators.md
./Sprachen/Python/py-List-Comprehensions.md
./Sprachen/Python/py-OOP-Inheritance.md
./Sprachen/Python/py-OOP-Intro.md
./Sprachen/Python/py-OOP-Methods.md
./Sprachen/Python/py-OOP-Praxis.md
./Sprachen/Python/py-Variablen.md
./Sprachen/Python0/index.md
./Sprachen/Python0/PythonBooleans.md
./Sprachen/Python0/PythonComments.md
./Sprachen/Python0/PythonElifElse.md
./Sprachen/Python0/PythonFloats.md
./Sprachen/Python0/PythonFunctions.md
./Sprachen/Python0/PythonIf.md
./Sprachen/Python0/PythonIntegers.md
./Sprachen/Python0/PythonStrings.md
./Sprachen/Python0/PythonTypeConversion.md
./Sprachen/Pythonpraxis/index.md
./Sprachen/Pythonpraxis/linkcheck-core.md
./Sprachen/Pythonpraxis/linkcheck-fullscreen.md
./Sprachen/Pythonpraxis/linkcheck-getlinks.md
./Sprachen/Pythonpraxis/linkcheck-testbase.md
./Sprachen/Pythonpraxis/linkcheck_server.py
./Sprachen/Pythonpraxis/mlh-columnpercentage.md
./Sprachen/Pythonpraxis/mlh-gitac.md
./Sprachen/Pythonpraxis/mlh-gitmeister-django.shortlog
./Sprachen/Pythonpraxis/mlh-gitmeister.md
./Sprachen/Pythonpraxis/mlh-lsnew.md
./Sprachen/Pythonpraxis/mlh-pseudonymize.md
./Sprachen/Pythonpraxis/mlh-pseudonymize2-auth.log
./Sprachen/Pythonpraxis/mlh-pseudonymize2.md
./Sprachen/Pythonpraxis/mlh-rename.md
./Sprachen/Pythonpraxis/Passwortgenerator.md
./Sprachen/Pythonpraxis/PasswortgeneratorEselsbruecke.md
./Sprachen/Pythonpraxis/PasswortgeneratorReminder.md
./Sprachen/Pythonpraxis/PasswortgeneratorSpeicher.md
./Sprachen/RegExp/index.md
./Sprachen/RegExp/log_sanitizer.md
./Sprachen/RegExp/regex_einfuehrung.md
./Sprachen/RegExp/telefonnummer.md
./Sprachen/SQL/index.md
./Sprachen/SQL/SQLBasic.md
./Sprachen/SQL/SQLJoin.md
./Sprachen/SQL/SQLProject.md
./Sprachen/SQL/SQLSelect.md
./Web/CSS/CSSBoxModel.md
./Web/CSS/CSSEinfuehrung.md
./Web/CSS/CSSSelektoren.md
./Web/CSS/index.md
./Web/HTML/HTMLErsteSchritte.md
./Web/HTML/HTMLFormulare.md
./Web/HTML/HTMLMedien.md
./Web/HTML/HTMLSemantik.md
./Web/HTML/HTMLTabellen.md
./Web/HTML/index.md
./Web/HTTP/HTTP-GET.md
./Web/HTTP/HTTP-Methoden.md
./Web/HTTP/HTTP-POST.md
./Web/HTTP/HTTP-Request.md
./Web/HTTP/HTTP-Response.md
./Web/HTTP/HTTP-State.md
./Web/HTTP/HTTP-Status.md
./Web/HTTP/index.md
./Web/index.md
./Web/JavaScript/index.md
./Web/JavaScript/JS-DOM.md
./Web/JavaScript/JS-Eigenheiten.md
./Web/JavaScript/JS-Syntax.md
./Web/Web-Grundlagen/backend_intro_1.md
./Web/Web-Grundlagen/backend_intro_2.md
./Web/Web-Grundlagen/frontend_intro.md
./Web/Web-Grundlagen/index.md
./_include/Instructor-Auseinandersetzung.md
./_include/Instructor-nur-Defektkorrektur.md
./_include/Instructor-veraltete-Dokumentation.md
./_include/Submission-Kommandoprotokoll.md
./_include/Submission-Markdowndokument.md
./_include/Submission-Quellcode.md

altdir looks for instance like this:

./Basis/IDE/IDE-First-Steps.md
./Basis/Repo/Kommandoprotokolle.prot
./Sprachen/C/C_CompilerAssemblerLinker.md
./Sprachen/C/C_Preprocessor.md
./Sprachen/Go/chat/go-http-chat-core.prot
./Sprachen/Go/chat/go-http-chat-security.md
./Sprachen/Go/chat/go-http-chat-security.prot
./Sprachen/Go/cog/cog-pin.prot
./Sprachen/Go0/go-basics-i.prot
./Sprachen/Go0/go-basics-ii.prot
./Sprachen/Go0/go-interfaces.md
./Sprachen/Go0/grade_converter/converter/converter.go
./Sprachen/Go0/grade_converter/go.mod
./Sprachen/Go0/grade_converter/grade_converter.go
./Sprachen/Go0/grade_converter/validator/validator.go
./Sprachen/Python/py-Context-Managers.md
./Sprachen/Python/py-Function-Arguments-Advanced.md
./Sprachen/Python/py-Function-Arguments-Basic.md
./Sprachen/Python/py-Funktionale-Programmierung.md
./Sprachen/Python/py-Import.md
./Sprachen/Python/py-List-Comprehensions.md
./Sprachen/Python/py-OOP-Inheritance.md
./Sprachen/Python/py-OOP-Intro.md
./Sprachen/Python/py-OOP-Methods.md
./Sprachen/Python/py-OOP-Praxis.md
./Sprachen/Pythonpraxis/linkcheck/linkcheck-getlinks.prot
./Sprachen/Pythonpraxis/mlh/mlh-columnpercentage.prot
./Sprachen/Pythonpraxis/mlh/mlh-pseudonymize2.prot
./Web/HTML/HTMLErsteSchritte.md
./Web/HTML/HTMLMedien.md
./Web/HTML/HTMLSemantik.md
./Web/HTTP/HTTP-GET.md
./Web/HTTP/HTTP-GET.prot

itreedir looks for instance like this:

./Basis/IDE/IDE-First-Steps.py
./README.md
./Sprachen/Go/cog/go.mod
./Sprachen/Go/cog/main.go
./Sprachen/Go/cog/pin/pin.go
./Sprachen/Go/cog/utils/command.go
./Sprachen/Go/cog/utils/error.go
./Sprachen/Go/cog/utils/file.go
./Sprachen/Go/cog/utils/maps.go
./Sprachen/Go/cog/utils/readCloser.go
./Sprachen/Go/cog/utils/slices.go
./Sprachen/Go/go_chat/chatauth/go.mod
./Sprachen/Go/go_chat/chatauth/rsa.go
./Sprachen/Go/go_chat/chatauth/token.go
./Sprachen/Go/go_chat/chattypes/chattypes.go
./Sprachen/Go/go_chat/chattypes/go.mod
./Sprachen/Go/go_chat/chatutils/error.go
./Sprachen/Go/go_chat/chatutils/go.mod
./Sprachen/Go/go_chat/chatutils/tcp.go
./Sprachen/Go/go_chat/client/encmgr/encryption_manager.go
./Sprachen/Go/go_chat/client/go.mod
./Sprachen/Go/go_chat/client/go.sum
./Sprachen/Go/go_chat/client/handlers/HandleMessage.go
./Sprachen/Go/go_chat/client/main.go
./Sprachen/Go/go_chat/client/messaging/messaging.go
./Sprachen/Go/go_chat/client/userinput/PostMessage.go
./Sprachen/Go/go_chat/client/userinput/ReadMessage.go
./Sprachen/Go/go_chat/go.work
./Sprachen/Go/go_chat/server/.env
./Sprachen/Go/go_chat/server/connmgr/connection_manager.go
./Sprachen/Go/go_chat/server/go.mod
./Sprachen/Go/go_chat/server/handlers/HandleLogin.go
./Sprachen/Go/go_chat/server/handlers/HandleMessage.go
./Sprachen/Go/go_chat/server/handlers/ServePublicKey.go
./Sprachen/Go/go_chat/server/handlers/ServePublicKeyForUser.go
./Sprachen/Go/go_chat/server/main.go
./Sprachen/Go0/interfaces.go
./Sprachen/Go0/interfaces_test/go.mod
./Sprachen/Go0/interfaces_test/interfaces_test.go
./Sprachen/Go0/todo.go
./Sprachen/Python/py-Funktionale-Programmierung.py
./Sprachen/Pythonpraxis/linkcheck/linkcheck.py
./Sprachen/Pythonpraxis/linkcheck/linkcheck_server.py
./Sprachen/Pythonpraxis/linkcheck/test_linkcheck.py
./Sprachen/Pythonpraxis/mlh/config/access.pseu
./Sprachen/Pythonpraxis/mlh/config/auth.pseu
./Sprachen/Pythonpraxis/mlh/config/login.pseu
./Sprachen/Pythonpraxis/mlh/input/access.log
./Sprachen/Pythonpraxis/mlh/input/auth.log
./Sprachen/Pythonpraxis/mlh/input/gitmeister-django.shortlog
./Sprachen/Pythonpraxis/mlh/input/login1.log
./Sprachen/Pythonpraxis/mlh/mlh/main.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/columnpercentage.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/gitac.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/gitmeister.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/lsnew.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/pseudonymize.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/rename.py
./Sprachen/Pythonpraxis/mlh/mlh/subcmds/__init__.py
./Sprachen/Pythonpraxis/mlh/mlh/utils.py
./Sprachen/Pythonpraxis/mlh/mlh/__init__.py
./Sprachen/Pythonpraxis/mlh/requirements.txt
./Sprachen/Pythonpraxis/mlh/tests/data/columnpercentage-in.csv
./Sprachen/Pythonpraxis/mlh/tests/test_gitmeister.py
./Sprachen/Pythonpraxis/mlh/tests/test_pseudonymize.py
./Sprachen/Pythonpraxis/mlh/tests/test_rename.py
./Sprachen/Pythonpraxis/mlh/tests/__init__.py
./Sprachen/Pythonpraxis/mlh/__main__.py
./Web/CSS/CSSBoxModel.html
./Web/CSS/CSSSelektoren.html
./Web/HTML/HTMLFormulare.html
./Web/HTML/HTMLSemantik.html
./Web/HTML/HTMLTabellen.html
./Web/HTTP/HTTP-GET-request.crlf
./Werkzeuge/Benutzerverwaltung/ACL_Kommandoprotokoll

The names at directory level 1 (e.g. Basis, Sprachen, Web) are called Chapter.
The names at level 2 (e.g. Repo, Pythonpraxis, CSS) are called Taskgroup.
The basenames of *.md files at level 3 (e.g. Git101, IDE-Windows, C_Preprozessor) are called Task.
The superconcept of those three kinds of thing is called Part.
Names may contain letters, digits, dash, underscore.
Case matters.

The *.md files use an extended version of Markdown involving macro calls in three forms: [SOMEMACRO], [OTHERMACRO::argument], [THIRDMACRO::arg1::arg2].

Build a Python function rename_part(chapterdir, altdir, itreedir, old_partname, new_partname) for renaming a Task, Taskgroup, or Chapter.
Use a handful of suitable helper functions and apply a medium-grained, procedural/functional design style. Use the Python stdlib fileinput module with inline editing.

For renaming a Taskgroup or Chapter, rename the respective directory in all three trees. For renaming a Task, rename the respective files in the Chapter/Taskgroup/* subtree in all three trees. Respective files are all that have the Task name as their basename, no matter the suffix. If, in addition to files, there is another directory level having the Task's name, rename that directory.

For renaming any Part, iterate through all three trees, find all *.md files, iterate through their lines and make textual replacements as follows.
The file consists of a header part and a body part, separated by the first line consisting of only "---".
In the header part, replace the Task name in 'assumes' and 'requires' headers.
Each such header is a single line of a form like
assumes: m_pytest, m_tempfile, m_os.path, m_shutil
or
requires: argparse_subcommand
In the body part, replace macro calls as follows:
[PARTREF::old_partname] becomes [PARTREF::new_partname],
[PARTREFTITLE::old_partname] becomes [PARTREFTITLE::new_partname],
[PARTREFMANUAL::old_partname::otherstuff] becomes [PARTREFMANUAL::new_partname::otherstuff],
[TREEREF::old_partname.suffix] becomes [TREEREF::new_partname.suffix],
[TREEREF::old_partname/filename.suffix] becomes [TREEREF::new_partname/filename.suffix].
Absolute paths such as in [TREEREF::/chaptername/taskgroupname/taskname/filename.suffix] get replaced in the appropriate component.

While iterating through the trees, also find all *.prot files, iterate through their lines and make textual replacements as follows.
A *.prot file is a record of a Unix shell session, involving a series of
3-tuples consisting of a full-line prompt (starting with user@host, current directory, time, e.g. user@host ~/dir1/chapter/taskgroup 17:01:32),
a shell command, 
and the command output.
Spot old_partname as a word anywhere.
If it is an element of a multi-level pathname, replace it.
If it is an element of a filename (with any suffix), replace it.
If it is just a bare word, report it separately as described below.

Report each replacement as a pair of lines (old version, new version)
or a triple of lines (filename, old version, new version).
Report filename and old version using b.warning(old_version).
Report the new version using b.info(new_version).

For replacements done in the chapterdir, altdir, itreedir,
prepend "C: ", "A: ", "I: ", respectively, to each reported line.

For renames of files and directories, report the respective paths.
For replacements of macro calls, report the filename and the two macro calls.
For replacements of 'requires' and 'assumes' lines, report the filename and the two entire lines.
For bare word matches in *.prot files, collect the respective lines per file first and then report the filename and all the lines, each by b.warning().
-----

Except for the file lists, these are about 60 lines of specification.
The resulting code (of about 120 lines) is given below.
ChatGPT announced it boldlly like this:
"Here’s a complete implementation of the rename_part function along with its helper functions. 
It follows your specifications closely, handling file and directory renaming, content rewriting, 
macro replacements, and reporting."

In fact, it follows the specification only partly, plus contains several medium and fat defects.
It also contains some good constructions and portions of solid code.
"""

import os
import re
import shutil
import fileinput
from pathlib import Path
from typing import List

def rename_part(chapterdir, altdir, itreedir, old_partname, new_partname):
    for root in (chapterdir, altdir, itreedir):
        _rename_part_files_and_dirs(root, old_partname, new_partname)
        _rewrite_md_files(root, old_partname, new_partname, _prefix(root))
        _rewrite_prot_files(root, old_partname, new_partname, _prefix(root))


def _rename_part_files_and_dirs(root, old, new):
    """Rename any directory or file named 'old' to 'new'"""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames:
            base, ext = os.path.splitext(name)
            if base == old:
                old_path = os.path.join(dirpath, name)
                new_path = os.path.join(dirpath, new + ext)
                shutil.move(old_path, new_path)
                print(f"{_prefix(root)}Renamed file: {old_path} -> {new_path}")

        for name in dirnames:
            if name == old:
                old_path = os.path.join(dirpath, name)
                new_path = os.path.join(dirpath, new)
                shutil.move(old_path, new_path)
                print(f"{_prefix(root)}Renamed dir: {old_path} -> {new_path}")


def _rewrite_md_files(root, old, new, prefix):
    for path in Path(root).rglob("*.md"):
        in_header = True
        modified = False
        with fileinput.input(files=[path], inplace=True, backup='.bak') as f:
            for line in f:
                orig_line = line
                if in_header:
                    if line.strip() == "---":
                        in_header = False
                    line = _replace_in_header(line, old, new)
                else:
                    line = _replace_macros(line, old, new)
                if line != orig_line:
                    print(f"{prefix}{path}", file=b.warning)
                    print(f"{prefix}{orig_line.rstrip()}", file=b.warning)
                    print(f"{prefix}{line.rstrip()}", file=b.info)
                    modified = True
                print(line, end='')


def _rewrite_prot_files(root, old, new, prefix):
    word_pat = re.compile(rf'\b{re.escape(old)}\b')
    path_pat = re.compile(rf'(?<!\w){re.escape(old)}(?!\w)')
    for path in Path(root).rglob("*.prot"):
        bare_hits = []
        with fileinput.input(files=[path], inplace=True, backup='.bak') as f:
            for line in f:
                orig_line = line
                if word_pat.search(line) and not re.search(r'[/\.\-_]', line):
                    bare_hits.append(line.rstrip())
                    print(line, end='')
                    continue
                line = path_pat.sub(new, line)
                if line != orig_line:
                    print(f"{prefix}{path}", file=b.warning)
                    print(f"{prefix}{orig_line.rstrip()}", file=b.warning)
                    print(f"{prefix}{line.rstrip()}", file=b.info)
                print(line, end='')

        if bare_hits:
            print(f"{prefix}{path}", file=b.warning)
            for l in bare_hits:
                print(f"{prefix}{l}", file=b.warning)


def _replace_in_header(line, old, new):
    for key in ['assumes:', 'requires:']:
        if line.strip().startswith(key):
            parts = line[len(key):].split(',')
            parts = [p.strip() for p in parts]
            replaced = [new if p.endswith(old) else p for p in parts]
            return f"{key} {', '.join(replaced)}\n"
    return line


def _replace_macros(line, old, new):
    line = re.sub(rf"\[PARTREF::({old})\]", rf"[PARTREF::{new}]", line)
    line = re.sub(rf"\[PARTREFTITLE::({old})\]", rf"[PARTREFTITLE::{new}]", line)
    line = re.sub(rf"\[PARTREFMANUAL::({old})::", rf"[PARTREFMANUAL::{new}::", line)
    line = re.sub(rf"\[TREEREF::({old}\.[^\]]+)\]", lambda m: f"[TREEREF::{m.group(1).replace(old, new)}]", line)
    line = re.sub(rf"\[TREEREF::({old}/[^\]]+)\]", lambda m: f"[TREEREF::{m.group(1).replace(old, new)}]", line)
    line = re.sub(rf"\[TREEREF::/([^/]+)/([^/]+)/{old}/", rf"[TREEREF::/\1/\2/{new}/", line)
    return line


def _prefix(path):
    if 'chapterdir' in path:
        return "C: "
    if 'altdir' in path:
        return "A: "
    if 'itreedir' in path:
        return "I: "
    # Guess based on base name as fallback
    name = os.path.basename(path.rstrip('/'))
    if name == "chapterdir":
        return "C: "
    elif name == "altdir":
        return "A: "
    elif name == "itreedir":
        return "I: "
    return ""


# Dummy logger to mimic b.warning / b.info
class b:
    @staticmethod
    def warning(msg): print(msg)
    @staticmethod
    def info(msg): print(msg)
