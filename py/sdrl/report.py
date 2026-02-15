"""Reports with statistics of course (for author) or student work (for student and instructor)."""
import dataclasses
import datetime as dt
import typing as tg

import base as b
import sdrl.html as h

if tg.TYPE_CHECKING:
    import sdrl.course


@dataclasses.dataclass
class Volumereport:
    """Data content of a report; column 1 is str, the others are numbers."""
    rows: list[tuple]
    columnheads: tg.Sequence[str]


# ----- author mode reports:

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


# ----- student/instructor mode reports:

def _has_been_worked_on(task: 'sdrl.course.Task') -> bool:
    return task.workhours > 0 or task.is_accepted or task.rejections > 0


def si_volume_report_per_chapter(course: 'sdrl.course.Course') -> Volumereport:
    return _si_volume_report(course, course.chapters, "Chapter",
                             lambda t, c: t.taskgroup.chapter == c, lambda c: c.name)


def si_volume_report_per_difficulty(course: 'sdrl.course.Course') -> Volumereport:
    from sdrl.course import Task
    return _si_volume_report(course, Task.DIFFICULTY_RANGE, "Difficulty",
                             lambda t, d: t.difficulty == d, lambda d: h.difficulty_levels[d-1])


def _si_volume_report(course: 'sdrl.course.Course', rowitems: tg.Iterable, column1head: str,
                      select: tg.Callable, render: tg.Callable) -> Volumereport:
    """Tuples of (category, worktime_sum, accept_sum, reject_sum)."""
    result = []
    for row in rowitems:
        tasks = [t for t in course.taskdict.values() if select(t, row) and _has_been_worked_on(t)]
        if not tasks:
            continue
        worktime = sum(t.workhours for t in tasks)
        accept = sum(t.timevalue for t in tasks if t.is_accepted)
        reject = sum(t.timevalue for t in tasks if t.rejections > 0 and not t.is_accepted)
        result.append((render(row), worktime, accept, reject))
    return Volumereport(result, (column1head, "Worktime", "Accept", "Reject"))


# ----- printing:

def print_volume_report(course: 'sdrl.course.Course', author_mode: bool):
    """Show volume reports: author mode shows all tasks, student/instructor mode shows worked-on tasks only."""
    if author_mode:
        _print_author_volume_report(course)
    else:
        _print_si_volume_report(course)


def _print_author_volume_report(course: 'sdrl.course.Course'):
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


def _print_si_volume_report(course: 'sdrl.course.Course'):
    """Show worktime, accepted, and rejected timevalues per difficulty and chapter."""
    for report in (si_volume_report_per_difficulty(course),
                   si_volume_report_per_chapter(course)):
        table = b.Table()
        for head in report.columnheads:
            justify = "left" if head == report.columnheads[0] else "right"
            table.add_column(head, justify=justify)
        total_worktime = total_accept = total_reject = 0.0
        for name, worktime, accept, reject in report.rows:
            table.add_row(name,
                          "%5.1f" % worktime,
                          "%5.1f" % accept,
                          "%5.1f" % reject)
            total_worktime += worktime
            total_accept += accept
            total_reject += reject
        table.add_row("[b]=TOTAL",
                      "[b]%5.1f" % total_worktime,
                      "[b]%5.1f" % total_accept,
                      "[b]%5.1f" % total_reject)
        b.rich_print(table)  # noqa
