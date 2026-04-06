"""Whitebox-ish tests for sdrl/report.py, based on simplistic proxies for Course/Chapter/Task."""
import types

import pytest

import sdrl.report as report
from sdrl.report import Volumereport


# ── naive test helpers ──────────────────────────────────────────────────────────────

def make_task(workhours=0, is_accepted=False, rejections=0, timevalue=1.0,
              to_be_skipped=False, difficulty=1, stage=None, chapter=None):
    chapter_obj = chapter or types.SimpleNamespace(name="ch1")
    task = types.SimpleNamespace(
        workhours=workhours,
        is_accepted=is_accepted,
        rejections=rejections,
        timevalue=timevalue,
        manual_timevalue=0.0,
        to_be_skipped=to_be_skipped,
        difficulty=difficulty,
        stage=stage,
        taskgroup=types.SimpleNamespace(chapter=chapter_obj),
    )
    return task


def make_course(tasks, chapters=None, stages=None, bonusrules=None):
    return types.SimpleNamespace(
        taskdict={f"task{i}": t for i, t in enumerate(tasks)},
        chapters=chapters or [],
        stages=stages or [],
        bonusrules=bonusrules,
    )


# ── Volumereport dataclass ────────────────────────────────────────────────────

def test_volumereport_stores_rows_and_columnheads():
    rows = [("A", 1, 2.0), ("B", 3, 4.5)]
    vr = Volumereport(rows=rows, columnheads=("Cat", "#Tasks", "Time"))
    assert vr.rows == rows
    assert vr.columnheads == ("Cat", "#Tasks", "Time")


# ── _has_been_worked_on ───────────────────────────────────────────────────────

def test_has_been_worked_on_workhours():
    assert report._has_been_worked_on(make_task(workhours=1.0))


def test_has_been_worked_on_accepted():
    assert report._has_been_worked_on(make_task(is_accepted=True))


def test_has_been_worked_on_rejected():
    assert report._has_been_worked_on(make_task(rejections=2))


def test_has_not_been_worked_on():
    assert not report._has_been_worked_on(make_task())


# ── _volume_report ────────────────────────────────────────────────────────────

def test_volume_report_counts_tasks_and_sums_timevalues():
    ch = types.SimpleNamespace(name="ch1")
    tasks = [
        make_task(timevalue=2.0, chapter=ch),
        make_task(timevalue=3.0, chapter=ch),
    ]
    course = make_course(tasks, chapters=[ch])
    result = report._volume_report(
        course, [ch], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
    )
    assert len(result.rows) == 1
    name, num_tasks, timevalue_sum = result.rows[0]
    assert name == "ch1"
    assert num_tasks == 2
    assert timevalue_sum == pytest.approx(5.0)


def test_volume_report_skips_to_be_skipped_tasks():
    ch = types.SimpleNamespace(name="ch1")
    tasks = [
        make_task(timevalue=2.0, chapter=ch, to_be_skipped=False),
        make_task(timevalue=5.0, chapter=ch, to_be_skipped=True),
    ]
    course = make_course(tasks, chapters=[ch])
    result = report._volume_report(
        course, [ch], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
    )
    _, num_tasks, timevalue_sum = result.rows[0]
    assert num_tasks == 1
    assert timevalue_sum == pytest.approx(2.0)


def test_volume_report_excludes_empty_rows_by_default():
    ch1 = types.SimpleNamespace(name="ch1")
    ch2 = types.SimpleNamespace(name="ch2")
    tasks = [make_task(timevalue=1.0, chapter=ch1)]
    course = make_course(tasks, chapters=[ch1, ch2])
    result = report._volume_report(
        course, [ch1, ch2], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
    )
    assert len(result.rows) == 1  # ch2 excluded (0 tasks)
    assert result.rows[0][0] == "ch1"


def test_volume_report_include_all_keeps_empty_rows():
    ch1 = types.SimpleNamespace(name="ch1")
    ch2 = types.SimpleNamespace(name="ch2")
    tasks = [make_task(timevalue=1.0, chapter=ch1)]
    course = make_course(tasks, chapters=[ch1, ch2])
    result = report._volume_report(
        course, [ch1, ch2], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
        include_all=True,
    )
    assert len(result.rows) == 2


def test_volume_report_returns_correct_columnheads():
    course = make_course([])
    result = report._volume_report(
        course, [], "Stage",
        select=lambda t, s: True,
        render=lambda s: str(s),
        include_all=False,
    )
    assert result.columnheads == ("Stage", "#Tasks", "Timevalue")


# ── _si_volume_report ─────────────────────────────────────────────────────────

def test_si_volume_report_sums_correctly():
    ch = types.SimpleNamespace(name="ch1")
    tasks = [
        make_task(workhours=2.0, is_accepted=True,  timevalue=3.0, chapter=ch),
        make_task(workhours=1.0, rejections=1,      timevalue=2.0, chapter=ch),
        make_task(workhours=0.0,                    timevalue=1.0, chapter=ch),  # not worked on
    ]
    course = make_course(tasks, chapters=[ch])
    result = report._si_volume_report(
        course, [ch], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
    )
    assert len(result.rows) == 1
    name, worktime, accept, reject, manual = result.rows[0]
    assert name == "ch1"
    assert worktime == pytest.approx(3.0)   # 2.0 + 1.0 (only worked-on tasks)
    assert accept == pytest.approx(3.0)     # accepted task timevalue
    assert reject == pytest.approx(2.0)     # rejected task timevalue


def test_si_volume_report_skips_unworked_rows():
    ch = types.SimpleNamespace(name="ch1")
    tasks = [make_task(chapter=ch)]  # no work done
    course = make_course(tasks, chapters=[ch])
    result = report._si_volume_report(
        course, [ch], "Chapter",
        select=lambda t, c: t.taskgroup.chapter == c,
        render=lambda c: c.name,
    )
    assert result.rows == []


def test_si_volume_report_columnheads():
    course = make_course([])
    result = report._si_volume_report(
        course, [], "Difficulty",
        select=lambda t, d: True,
        render=lambda d: str(d),
    )
    assert result.columnheads == ("Difficulty", "Worktime", "Accept", "Reject", "Manual")


# ── volume_report_per_stage ───────────────────────────────────────────────────

def test_volume_report_per_stage_includes_none_stage():
    tasks = [make_task(timevalue=1.5, stage=None)]
    course = make_course(tasks, stages=[])
    result = report.volume_report_per_stage(course)
    assert any(name == "done" for name, _, _ in result.rows)


# ── wrapper functions ─────────────────────────────────────────────────────────

def test_volume_report_per_chapter():
    ch = types.SimpleNamespace(name="mychapter")
    tasks = [make_task(timevalue=2.5, chapter=ch)]
    course = make_course(tasks, chapters=[ch])
    result = report.volume_report_per_chapter(course)
    assert result.columnheads[0] == "Chapter"
    assert result.rows[0][0] == "mychapter"
    assert result.rows[0][2] == pytest.approx(2.5)


def test_volume_report_per_difficulty(monkeypatch):
    import sdrl.html as h
    import sdrl.course
    monkeypatch.setattr(h, 'difficulty_levels', ['easy', 'medium', 'hard'])

    class FakeTask:
        DIFFICULTY_RANGE = [1, 2, 3]
    monkeypatch.setattr(sdrl.course, 'Task', FakeTask)

    tasks = [make_task(timevalue=1.0, difficulty=2)]
    course = make_course(tasks)
    result = report.volume_report_per_difficulty(course)
    assert result.columnheads[0] == "Difficulty"
    assert any(name == "medium" for name, _, _ in result.rows)


def test_si_volume_report_per_chapter():
    ch = types.SimpleNamespace(name="mychapter")
    tasks = [make_task(workhours=1.0, timevalue=2.0, chapter=ch)]
    course = make_course(tasks, chapters=[ch])
    result = report.si_volume_report_per_chapter(course)
    assert result.columnheads[0] == "Chapter"
    assert result.rows[0][0] == "mychapter"


def test_si_volume_report_per_difficulty(monkeypatch):
    import sdrl.html as h
    import sdrl.course
    monkeypatch.setattr(h, 'difficulty_levels', ['easy', 'medium', 'hard'])

    class FakeTask:
        DIFFICULTY_RANGE = [1, 2, 3]
    monkeypatch.setattr(sdrl.course, 'Task', FakeTask)

    tasks = [make_task(workhours=1.0, timevalue=2.0, difficulty=1)]
    course = make_course(tasks)
    result = report.si_volume_report_per_difficulty(course)
    assert result.columnheads[0] == "Difficulty"
    assert any(name == "easy" for name, _, _, _, _ in result.rows)


# ── print_author_volume_report ────────────────────────────────────────────────

def test_print_author_volume_report_csv_format(monkeypatch, capsys):
    fake_stage = Volumereport(rows=[("done", 2, 5.0), ("beta", 1, 1.5)],
                              columnheads=("Stage", "#Tasks", "Timevalue"))
    fake_empty = Volumereport(rows=[], columnheads=("X", "#Tasks", "Timevalue"))

    monkeypatch.setattr(report, 'volume_report_per_stage',      lambda c: fake_stage)
    monkeypatch.setattr(report, 'volume_report_per_difficulty', lambda c: fake_empty)
    monkeypatch.setattr(report, 'volume_report_per_chapter',    lambda c: fake_empty)

    report.print_author_volume_report(types.SimpleNamespace())
    out, _ = capsys.readouterr()
    assert "date,done,beta" in out
    assert "5.00" in out
    assert "1.50" in out
