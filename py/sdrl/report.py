"""Reports with statistics of course (for author) or student work (for student and instructor)."""
import dataclasses
import datetime as dt
import typing as tg

import base as b
import sdrl.html as h

if tg.TYPE_CHECKING:
    import sdrl.course
    import sdrl.course_si
    import sdrl.participant


@dataclasses.dataclass
class Volumereport:
    """Data content of a report; column 1 is str, the others are numbers."""
    rows: list[tuple]  # name, worktime, accept, reject, manual
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


def _has_manual_bookings(task: 'sdrl.course.Task') -> bool:
    # Zeros despite multiple bookings will be very rare; task bookings are usually negative:
    return task.manual_timevalue != 0.0


def si_volume_report_per_chapter(course: 'sdrl.course_si.CourseSI') -> Volumereport:
    return _si_volume_report(course, course.chapters, "Chapter",
                             lambda t, c: t.taskgroup.chapter == c, lambda c: c.name)


def si_volume_report_per_difficulty(course: 'sdrl.course_si.CourseSI') -> Volumereport:
    from sdrl.course import Task
    return _si_volume_report(course, Task.DIFFICULTY_RANGE, "Difficulty",
                             lambda t, d: t.difficulty == d, lambda d: h.difficulty_levels[d-1])


def _si_volume_report(course: 'sdrl.course_si.CourseSI', rowitems: tg.Iterable, column1head: str,
                      select: tg.Callable, render: tg.Callable) -> Volumereport:
    """Tuples of (category, worktime_sum, accept_sum, reject_sum, manual_sum)."""
    result = []
    for row in rowitems:
        tasks = [t for t in course.taskdict.values()
                 if select(t, row) and (_has_been_worked_on(t) or _has_manual_bookings(t))]
        if not tasks:
            continue
        worktime = sum(t.workhours for t in tasks)
        accept = sum(t.timevalue for t in tasks if t.is_accepted)
        reject = sum(t.timevalue for t in tasks if t.rejections > 0 and not t.is_accepted)
        manual = sum(t.manual_timevalue for t in tasks)
        result.append((render(row), worktime, accept, reject, manual))
    return Volumereport(result, (column1head, "Worktime", "Accept", "Reject", "Manual"))


# ----- printing:

def print_author_volume_report(course: 'sdrl.course.Course'):
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


def print_si_volume_report(student: 'sdrl.participant.Student'):
    """Show worktime, accepted, and rejected timevalues per difficulty and chapter."""
    import sdrl.course_si
    course = student.course_with_work
    # Compute global manual bookings (those not task-specific)
    task_manual_sum = sum(t.manual_timevalue for t in course.taskdict.values())
    global_manual = course.manual_timevalue - task_manual_sum
    for report in (si_volume_report_per_difficulty(course),
                   si_volume_report_per_chapter(course)):
        table = b.Table()
        for head in report.columnheads:
            justify = "left" if head == report.columnheads[0] else "right"
            table.add_column(head, justify=justify)
        total_worktime = total_accept = total_reject = total_manual = 0.0
        for name, worktime, accept, reject, manual in report.rows:
            table.add_row(name,
                          "%5.1f" % worktime,
                          "%5.1f" % accept,
                          "%5.1f" % reject,
                          "%5.1f" % manual if manual else "")
            total_worktime += worktime
            total_accept += accept
            total_reject += reject
            total_manual += manual
        # Add bonus row if bonusrules are configured
        total_bonus = 0.0
        if course.bonusrules is not None:
            attr = course.bonusrules['student_yaml_attribute']
            raw = student.participant_data.get(attr)
            if raw is not None:
                course_size_hours = float(raw)
                results = course.compute_bonus(course_size_hours)
                total_bonus = sdrl.course_si.CourseSI.total_bonus(results)
                if total_bonus:
                    table.add_row("[i]Bonus", "", "[i]%5.1f" % total_bonus, "", "")
        # Add "other manual bookings" row
        if global_manual:
            table.add_row("[i]other manual bookings", "", "", "", "[i]%5.1f" % global_manual)
            total_manual += global_manual
        table.add_row("[b]=TOTAL",
                      "[b]%5.1f" % total_worktime,
                      "[b]%5.1f" % (total_accept + total_bonus),
                      "[b]%5.1f" % total_reject,
                      "[b]%5.1f" % total_manual)
        b.rich_print(table)  # noqa
    # Grand total line after the last table
    grand_total = total_accept + total_bonus + course.manual_timevalue
    print(f"Grand total course work timevalue: {grand_total:.1f}h")
