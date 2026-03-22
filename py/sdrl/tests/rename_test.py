import logging
import os

import pytest

import base as b
import sdrl.rename
from sdrl.rename import _Collector


def setup_function():
    b._testmode_reset()
    b.loglevel = logging.INFO


# ── _replace_requires_assumes ─────────────────────────────────────────────────

def test_replace_requires_assumes():
    def r_ra(line):
        return sdrl.rename._replace_requires_assumes(line, "ol-d", "new")

    # ----- matches:
    assert r_ra("assumes: ol-d") == "assumes: new"
    assert r_ra("requires: a,  ol-d,b") == "requires: a,  new,b"
    assert r_ra("requires:ol-d") == "requires:new"

    # ----- non-matches:
    assert r_ra(" assumes: ol-d") == " assumes: ol-d"
    assert r_ra("assumes ol-d") == "assumes ol-d"
    assert r_ra("assumes: aol-d") == "assumes: aol-d"
    assert r_ra("assumes: ol-d-e") == "assumes: ol-d-e"


# ── _replace_macros ───────────────────────────────────────────────────────────

def test_replace_macros():
    def r_m3(line, oldname, newname):
        return sdrl.rename._replace_macros(line, oldname, newname)
    def r_m(line):
        return r_m3(line, "ol-d", "new")

    # ----- matches:
    assert r_m("a [PARTREF::ol-d] b") == "a [PARTREF::new] b"
    assert r_m("a[PARTREF2::ol-d::manualstuff]b") == "a[PARTREF2::new::manualstuff]b"
    assert r_m("[INCLUDE::ol-d]") == "[INCLUDE::new]"
    assert r_m("[INCLUDE::/a/b/ol-d/c]") == "[INCLUDE::/a/b/new/c]"
    assert r_m("[INCLUDE::ol-d/c]") == "[INCLUDE::new/c]"
    assert r_m("[INCLUDE::/a/b/ol-d]") == "[INCLUDE::/a/b/new]"
    assert r_m("[INCLUDE::ALT:/a/b/ol-d/c]") == "[INCLUDE::ALT:/a/b/new/c]"
    assert r_m("[INCLUDE::ALT:ol-d/c]") == "[INCLUDE::ALT:new/c]"
    assert r_m("[INCLUDE::ALT:/a/b/ol-d]") == "[INCLUDE::ALT:/a/b/new]"
    assert r_m("[TREEREF::ol-d/c]") == "[TREEREF::new/c]"
    assert r_m("[PROT::ALT:/a/b/ol-d]") == "[PROT::ALT:/a/b/new]"
    assert r_m3("[PARTREF::abc_d_ef]", "abc_d_ef", "hijk") == "[PARTREF::hijk]"
    # ----- non-matches:
    assert r_m("[INCLUDE::ol-de]") == "[INCLUDE::ol-de]"
    assert r_m("[INCLUDE::a-ol-d]") == "[INCLUDE::a-ol-d]"


# ── _replace_protline ─────────────────────────────────────────────────────────

def test_rewrite_prot():
    def r_p(line):
        return sdrl.rename._replace_protline(line, "ol-d", "new")

    # ----- matches:
    assert r_p("ol-d") == "new"
    assert r_p("user@host ~/abc/ol-d ") == "user@host ~/abc/new "
    assert r_p("user@host ~/abc/ol-d/def") == "user@host ~/abc/new/def"
    assert r_p("python ol-d.py") == "python new.py"
    # ----- non-matches:
    assert r_p("ol-d-e") == "ol-d-e"
    assert r_p("a-ol-d") == "a-ol-d"


# ── _Collector ────────────────────────────────────────────────────────────────

def test_collector_record_groups_by_filepath():
    c = _Collector()
    c.record('headers_replaced', 'file.md', 'line1')
    c.record('headers_replaced', 'file.md', 'line2')
    c.record('headers_replaced', 'other.md', 'line3')
    assert c.headers_replaced == {'file.md': ['line1', 'line2'], 'other.md': ['line3']}


def test_collector_initial_state():
    c = _Collector()
    assert c.files_renamed == []
    assert c.dirs_renamed == []
    assert c.md_files == []
    assert c.prot_files == []
    assert c.headers_replaced == {}
    assert c.macros_replaced == {}
    assert c.protlines_replaced == {}


# ── _rename_and_collect_across ────────────────────────────────────────────────

def _make_tree(root, structure: dict):
    """Recursively create files and dirs from a dict {name: content_or_subdict}."""
    for name, content in structure.items():
        path = os.path.join(root, name)
        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            _make_tree(path, content)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wt', encoding='utf8') as f:
                f.write(content)


def test_rename_and_collect_renames_dir(tmp_path):
    _make_tree(str(tmp_path), {
        "oldname": {"file.md": "content"},
    })
    c = _Collector()
    sdrl.rename._rename_and_collect_across(str(tmp_path), "oldname", "newname", c)
    assert not os.path.exists(str(tmp_path / "oldname"))
    assert os.path.isdir(str(tmp_path / "newname"))
    assert len(c.dirs_renamed) == 1
    assert "newname" in c.dirs_renamed[0]


def test_rename_and_collect_renames_file(tmp_path):
    _make_tree(str(tmp_path), {
        "oldname.md": "assumes: other",
    })
    c = _Collector()
    sdrl.rename._rename_and_collect_across(str(tmp_path), "oldname", "newname", c)
    assert not os.path.exists(str(tmp_path / "oldname.md"))
    assert os.path.exists(str(tmp_path / "newname.md"))
    assert len(c.files_renamed) == 1


def test_rename_and_collect_collects_md_files(tmp_path):
    _make_tree(str(tmp_path), {
        "other.md": "content",
        "unrelated.txt": "text",
    })
    c = _Collector()
    sdrl.rename._rename_and_collect_across(str(tmp_path), "oldname", "newname", c)
    assert any("other.md" in f for f in c.md_files)
    assert not any(".txt" in f for f in c.md_files)


def test_rename_and_collect_skips_hidden_dirs(tmp_path):
    _make_tree(str(tmp_path), {
        ".hidden": {"oldname.md": "content"},
    })
    c = _Collector()
    sdrl.rename._rename_and_collect_across(str(tmp_path), "oldname", "newname", c)
    assert os.path.exists(str(tmp_path / ".hidden" / "oldname.md"))  # untouched
    assert c.md_files == []


def test_rename_and_collect_prot_file_collected(tmp_path):
    _make_tree(str(tmp_path), {
        "oldname.prot": "some prot content",
    })
    c = _Collector()
    sdrl.rename._rename_and_collect_across(str(tmp_path), "oldname", "newname", c)
    assert any("newname.prot" in f for f in c.prot_files)


# ── _process_markdown_files ───────────────────────────────────────────────────

def test_process_markdown_files_replaces_content(tmp_path):
    md = tmp_path / "task.md"
    md.write_text("assumes: oldpart\n[PARTREF::oldpart]\n", encoding='utf8')
    c = _Collector()
    c.md_files.append(str(md))
    sdrl.rename._process_markdown_files(c, "oldpart", "newpart")
    result = md.read_text(encoding='utf8')
    assert "oldpart" not in result
    assert "newpart" in result


def test_process_markdown_files_no_change_not_written(tmp_path):
    md = tmp_path / "task.md"
    original = "no mentions of the old name here\n"
    md.write_text(original, encoding='utf8')
    mtime_before = os.stat(str(md)).st_mtime
    c = _Collector()
    c.md_files.append(str(md))
    sdrl.rename._process_markdown_files(c, "oldpart", "newpart")
    mtime_after = os.stat(str(md)).st_mtime
    assert mtime_before == mtime_after  # file not touched


# ── _process_prot_files ───────────────────────────────────────────────────────

def test_process_prot_files_replaces_content(tmp_path):
    prot = tmp_path / "newpart.prot"
    prot.write_text("user@host ~/work/oldpart\n", encoding='utf8')
    c = _Collector()
    c.prot_files.append(str(prot))
    sdrl.rename._process_prot_files(c, "oldpart", "newpart")
    result = prot.read_text(encoding='utf8')
    assert "oldpart" not in result
    assert "newpart" in result


# ── rename_part (integration) ─────────────────────────────────────────────────

def test_rename_part_end_to_end(tmp_path):
    chapterdir = tmp_path / "ch"
    altdir = tmp_path / "alt"
    itreedir = tmp_path / "itree"
    for d in [chapterdir, altdir, itreedir]:
        d.mkdir()
    _make_tree(str(chapterdir), {
        "oldpart": {
            "oldpart.md": "assumes: oldpart\n[PARTREF::oldpart]\n",
        },
        "other.md": "requires: oldpart\n",
    })
    sdrl.rename.rename_part(
        str(chapterdir), str(altdir), str(itreedir), "oldpart", "newpart"
    )
    assert os.path.isdir(str(chapterdir / "newpart"))
    assert os.path.exists(str(chapterdir / "newpart" / "newpart.md"))
    assert not os.path.exists(str(chapterdir / "oldpart"))
    other_content = (chapterdir / "other.md").read_text(encoding='utf8')
    assert "oldpart" not in other_content
    assert "newpart" in other_content
