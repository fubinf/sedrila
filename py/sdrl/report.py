"""Volume reports for course statistics."""
import dataclasses
import datetime as dt
import typing as tg

import base as b
import sdrl.html as h

if tg.TYPE_CHECKING:
    import sdrl.course


@dataclasses.dataclass
class Volumereport:
    rows: tg.Sequence[tg.Tuple[str, int, float]]
    columnheads: tg.Sequence[str]


def volume_report_per_chapter(course: 'sdrl.course.Course') -> Volumereport:
    return _volume_report(course, course.chapters, "Chapter",
                          lambda t, c: t.taskgroup.chapter == c, lambda c: c.name)


def volume_report_per_difficulty(course: 'sdrl.course.Course') -> Volumereport:
    from sdrl.course import Task
    return _volume_report(course, Task.DIFFICULTY_RANGE, "Difficulty",
                          lambda t, d: t.difficulty == d, lambda d: h.difficulty_levels[d-1])


def volume_report_per_stage(course: 'sdrl.course.Course') -> Volumereport:
    return _volume_report(course, course.stages + [None], "Stage",
                          lambda t, s: t.stage == s, lambda s: s or "done", include_all=True)


def _volume_report(course: 'sdrl.course.Course', rowitems: tg.Iterable, column1head: str,
                   select: tg.Callable, render: tg.Callable,
                   include_all=False) -> Volumereport:
    """Tuples of (category, num_tasks, timevalue_sum)."""
    result = []
    for row in rowitems:
        num_tasks = sum((1 for t in course.taskdict.values() if select(t, row) and not t.to_be_skipped))
        timevalue_sum = sum((t.timevalue for t in course.taskdict.values() if select(t, row) and not t.to_be_skipped))
        if num_tasks > 0 or include_all:
            result.append((render(row), num_tasks, timevalue_sum))
    return Volumereport(result, (column1head, "#Tasks", "Timevalue"))


def print_volume_report(course: 'sdrl.course.Course'):
    """Show total timevalues per stage, difficulty, and chapter."""
    # ----- print cumulative timevalues per stage as comma-separated values (CSV):
    report_per_stage = volume_report_per_stage(course)
    print("date", end="")
    for stage, numtasks, timevalue in report_per_stage.rows:
        print(f",{stage}", end="")
    print("")  # newline
    print(dt.date.today().strftime("%Y-%m-%d"), end="")
    for stage, numtasks, timevalue in report_per_stage.rows:
        print(",%.2f" % timevalue, end="")
    print("")  # newline

    # ----- print all reports as rich tables:
    for report in (report_per_stage,
                   volume_report_per_difficulty(course),
                   volume_report_per_chapter(course)):
        table = b.Table()
        table.add_column(report.columnheads[0])
        table.add_column(report.columnheads[1], justify="right")
        table.add_column(report.columnheads[2], justify="right")
        totaltasks = totaltime = 0
        for name, numtasks, timevalue in report.rows:
            table.add_row(name,
                          str(numtasks),
                          "%5.1f" % timevalue)
            totaltasks += numtasks
            totaltime += timevalue
        table.add_row("[b]=TOTAL", f"[b]{totaltasks}", "[b]%5.1f" % totaltime)
        b.rich_print(table)  # noqa
