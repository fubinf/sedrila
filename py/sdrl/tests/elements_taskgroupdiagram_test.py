"""Whitebox-ish unit tests for sdrl.elements.TaskgroupDiagram."""
import logging
import os
import shutil
import unittest.mock as mock

import base as b
import cache as c
import sdrl.directory as dir
import sdrl.elements as el

TESTDIR = "py/sdrl/tests/elements_taskgroupdiagram_tmp"


def setup_function():
    b._testmode_reset()  # noqa
    b.loglevel = logging.ERROR
    shutil.rmtree(TESTDIR, ignore_errors=True)
    os.makedirs(f"{TESTDIR}/s")
    os.makedirs(f"{TESTDIR}/i")


def teardown_function():
    shutil.rmtree(TESTDIR, ignore_errors=True)


# ── fakes ─────────────────────────────────────────────────────────────────────

class _FakeTopmatter:
    """Stand-in for el.Topmatter: only the interface TaskgroupDiagram relies on."""
    def __init__(self, name: str, value: dict, state=c.State.AS_BEFORE):
        self.name = name
        self.value = value
        self.state = state

    def has_value(self) -> bool:
        return True

    @property
    def statelabel(self) -> str:
        return str(self.state)


class _FakeTask:
    """Stand-in for a Taskbuilder, as it looks after MetadataDerivation has run."""
    def __init__(self, name, assumes=(), requires=(), difficulty=1, to_be_skipped=False):
        self.name = name
        self.assumes = list(assumes)
        self.requires = list(requires)
        self.difficulty = difficulty
        self.title = f"Title of {name}"
        self.to_be_skipped = to_be_skipped

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"


class _FakeCourse:
    def __init__(self, tasks: list[_FakeTask]):
        self.taskdict = {t.name: t for t in tasks}


class _FakeTaskgroup:
    """Stand-in for a Taskgroupbuilder: satisfies what Element._inherit_from_part() needs."""
    def __init__(self, directory: dir.Directory, tasks: list[_FakeTask],
                 alltasks: list[_FakeTask] = None, to_be_skipped=False):
        self.directory = directory
        self.sourcefile = "fake/tg1/index.md"
        self.tasks = tasks  # the taskgroup's own tasks
        self.to_be_skipped = to_be_skipped
        self.course = _FakeCourse(alltasks if alltasks is not None else tasks)


# ── helpers ───────────────────────────────────────────────────────────────────

CACHEFILE = f"{TESTDIR}/cache"


def _make_cache(start_clean: bool) -> c.SedrilaCache:
    # a real (file-backed) cache, so a second SedrilaCache instance sees what a first one wrote,
    # exactly like two successive process runs would:
    return c.SedrilaCache(cache_filename=CACHEFILE, start_clean=start_clean)


def _register_topmatter(directory: dir.Directory, taskname: str, value: dict,
                        state=c.State.AS_BEFORE):
    directory.take_the(el.Topmatter, taskname, _FakeTopmatter(taskname, value, state))


def _make_diagram(directory: dir.Directory, taskgroup: _FakeTaskgroup) -> el.TaskgroupDiagram:
    return directory.make_the(el.TaskgroupDiagram, "tg1", part=taskgroup,
                              targetdir_s=f"{TESTDIR}/s", targetdir_i=f"{TESTDIR}/i")


def _setup(start_clean: bool, tasks: list[_FakeTask], alltasks: list[_FakeTask] = None,
           topmatter_states: dict[str, c.State] = None, to_be_skipped=False):
    """Build cache, Directory, taskgroup, Topmatters, and diagram for one simulated process run."""
    cache = _make_cache(start_clean=start_clean)
    directory = dir.Directory(cache)
    taskgroup = _FakeTaskgroup(directory, tasks, alltasks, to_be_skipped)
    for taskname, task in taskgroup.course.taskdict.items():
        state = (topmatter_states or dict()).get(taskname, c.State.AS_BEFORE)
        _register_topmatter(directory, taskname, dict(title=task.title, difficulty=task.difficulty), state)
    return cache, _make_diagram(directory, taskgroup)


# ── the tasks shown ───────────────────────────────────────────────────────────

def test_externaltasks_are_the_assumed_and_required_ones_only():
    g1 = _FakeTask("g1", assumes=["ext_a"])
    g2 = _FakeTask("g2", requires=["ext_r"], assumes=["g1", "nonexisting"])
    externals = [_FakeTask("ext_a"), _FakeTask("ext_r"),
                 _FakeTask("ext_dependent", assumes=["g1"]),  # depends on us, must not show up
                 _FakeTask("ext_unrelated")]
    cache, diagram = _setup(start_clean=True, tasks=[g2, g1], alltasks=[g1, g2] + externals)
    diagram.check_existing_resource()
    assert diagram.grouptasks == ["g1", "g2"]
    assert diagram.externaltasks == ["ext_a", "ext_r"]  # sorted, no dependents, no dangling 'nonexisting'
    assert sorted(dep.name for dep in diagram.my_dependencies()) == ["ext_a", "ext_r", "g1", "g2"]


def test_edges_lead_from_the_assumed_or_required_task_to_the_grouptask():
    g1 = _FakeTask("g1", assumes=["ext_a"])
    g2 = _FakeTask("g2", requires=["ext_r"], assumes=["g1"])
    externals = [_FakeTask("ext_a"), _FakeTask("ext_r"), _FakeTask("ext_dependent", assumes=["g1"])]
    cache, diagram = _setup(start_clean=True, tasks=[g1, g2], alltasks=[g1, g2] + externals)
    diagram.build()
    svg = b.slurp(diagram.outputfile_s)
    assert "<title>ext_a&#45;&gt;g1</title>" in svg  # g1 assumes ext_a
    assert "<title>ext_r&#45;&gt;g2</title>" in svg  # g2 requires ext_r
    assert "<title>g1&#45;&gt;g2</title>" in svg  # g2 assumes g1
    assert "ext_dependent" not in svg  # it assumes g1, but that is not what we show


# ── first build ───────────────────────────────────────────────────────────────

def test_first_build_is_missing_and_renders_svg():
    cache, diagram = _setup(start_clean=True, tasks=[_FakeTask("t1"), _FakeTask("t2", difficulty=2)])
    diagram.check_existing_resource()
    assert diagram.state == c.State.MISSING
    diagram.build()
    assert diagram.state == c.State.HAS_CHANGED  # MISSING turns into HAS_CHANGED once built
    assert os.path.exists(diagram.outputfile_s)
    assert os.path.exists(diagram.outputfile_i)
    svg = b.slurp(diagram.outputfile_s)
    assert "t1" in svg and "t2" in svg
    assert 'xlink:href="t2.html"' in svg  # nodes link to their task page


# ── no-op rebuild ─────────────────────────────────────────────────────────────

def test_second_run_unchanged_is_as_before_and_skips_do_build():
    # ----- run 1: build from scratch:
    cache1, diagram1 = _setup(start_clean=True, tasks=[_FakeTask("t1"), _FakeTask("t2")])
    diagram1.build()
    cache1.close()  # persist, like a real build does at the end
    # ----- run 2: nothing changed, fresh cache+Directory reading persisted state (like a fresh process):
    cache2, diagram2 = _setup(start_clean=False, tasks=[_FakeTask("t1"), _FakeTask("t2")])
    with mock.patch.object(el.TaskgroupDiagram, "do_build") as mock_do_build:
        diagram2.build()
        mock_do_build.assert_not_called()
    assert diagram2.state == c.State.AS_BEFORE


# ── rebuild on dependency change (e.g. an assumes/requires/difficulty edit) ────

def test_rebuild_when_a_topmatter_dependency_has_changed():
    cache1, diagram1 = _setup(start_clean=True, tasks=[_FakeTask("t1"), _FakeTask("t2")])
    diagram1.build()
    cache1.close()
    # ----- run 2: t2's topmatter reports HAS_CHANGED (e.g. its 'assumes' list changed):
    cache2, diagram2 = _setup(start_clean=False, tasks=[_FakeTask("t1"), _FakeTask("t2")],
                              topmatter_states=dict(t2=c.State.HAS_CHANGED))
    with mock.patch.object(el.TaskgroupDiagram, "do_build", wraps=diagram2.do_build) as mock_do_build:
        diagram2.build()
        mock_do_build.assert_called_once()


def test_rebuild_when_an_external_topmatter_dependency_has_changed():
    g1 = _FakeTask("g1", assumes=["ext_a"])
    ext_a = _FakeTask("ext_a")
    cache1, diagram1 = _setup(start_clean=True, tasks=[g1], alltasks=[g1, ext_a])
    diagram1.build()
    cache1.close()
    # ----- run 2: the external task's topmatter reports HAS_CHANGED (e.g. its difficulty changed):
    cache2, diagram2 = _setup(start_clean=False, tasks=[g1], alltasks=[g1, ext_a],
                              topmatter_states=dict(ext_a=c.State.HAS_CHANGED))
    with mock.patch.object(el.TaskgroupDiagram, "do_build", wraps=diagram2.do_build) as mock_do_build:
        diagram2.build()
        mock_do_build.assert_called_once()


# ── rebuild on task removal (node-set diffing, not covered by plain dependency propagation) ──

def test_rebuild_when_a_task_is_removed_from_the_taskgroup():
    cache1, diagram1 = _setup(start_clean=True, tasks=[_FakeTask("t1"), _FakeTask("t2")])
    diagram1.build()
    cache1.close()
    # ----- run 2: t2 is gone, t1's topmatter is unchanged (AS_BEFORE):
    cache2, diagram2 = _setup(start_clean=False, tasks=[_FakeTask("t1")])
    diagram2.check_existing_resource()
    assert diagram2.state == c.State.HAS_CHANGED
    diagram2.build()
    svg = b.slurp(diagram2.outputfile_s)
    assert "t2" not in svg


# ── skipped taskgroup ─────────────────────────────────────────────────────────

def test_skipped_taskgroup_gets_no_diagram():
    cache, diagram = _setup(start_clean=True, tasks=[_FakeTask("t1")], to_be_skipped=True)
    with mock.patch.object(el.TaskgroupDiagram, "do_build") as mock_do_build:
        diagram.build()
        mock_do_build.assert_not_called()
    assert diagram.state == c.State.AS_BEFORE
    assert not os.path.exists(diagram.outputfile_s)


# ── missing 'dot' executable fallback ───────────────────────────────────────────

def test_missing_dot_executable_falls_back_to_placeholder_svg():
    cache, diagram = _setup(start_clean=True, tasks=[_FakeTask("t1")])
    with mock.patch.object(el.TaskgroupDiagram, "_render_svg_via_graphviz",
                           side_effect=OSError("dot executable not found")):
        diagram.build()
    svg = b.slurp(diagram.outputfile_s)
    assert "graphviz" in svg and "<svg" in svg
