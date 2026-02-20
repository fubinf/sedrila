"""
Statistical evaluation (by a course organizer/course developer) of the progress of 
an entire course cohort.

Goals:
- Understand difficulty level distribution across the students.
- Understand what tasks/taskgroups are most popular or unpopular
- Identify tasks with too-low or too-high time value (via worktime) or difficulty (via resubmissions).
- Understand re-submission behavior patterns (per people, per tasks, over time).
- Understand typical orderings in which taskgroups are chosen in the students' work
- Understand work time patterns (workdays, weekly trends, submission intervals, etc.)
- Understand submission patterns (intensity over time, submission size)
- Understand load distribution among instructors

Expect 100-500 different tasks, 50-80 taskgroups, 10-20 chapters,
30-500 students, 2-5 instructors,
14-52 weeks course duration, time values in range 0.5h to 4h (with rare exceptions up to 50h,
it is OK to cut those off),
resubmission of tasks allowed once per task, rejection rates of 0-20%.

Eventually, this should have the following properties:
- runs a webserver (as webapp.py does) to display all evaluations as a single, long webpage
- the page starts with an overview (link list) of the evaluations
- uses mostly plots (with good titles above and concise explanatory text below), but also some textual presentations
- plots often use the quartile format like plot_weekly_student_quantiles() does
- besides such time series plots, categorical ones (e.g. a few stacked barcharts) are useful,
  and maybe a small number of other types
- plot types are mostly used more than once, their code avoids duplication (generic plot routines
  parameterized with data extraction functions or so) 
- plots can use absolute numbers or percentages
- color palettes are configurable
"""
import contextlib
import datetime as dt
import glob
import html
import os
import pickle
import typing as tg

import argparse_subcommand as ap_sub
import matplotlib.pyplot as plt
import pandas
import pandas as pd

import base as b
import sgit
import sdrl.constants as c
import sdrl.course
import sdrl.participant
import sdrl.repo as repo

meaning = """Statistical evaluation of the progress of an entire course cohort."""


def add_arguments(subparser: ap_sub.ArgumentParser):
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")
    subparser.add_argument('--nopull', action='store_true',
                           help="Skip the 'git pull' in each repsitory subdir")
    subparser.add_argument('startdate',
                           help="day 1 of the course as yyyy-mm-dd")
    subparser.add_argument('outputdir',
                           help="where to put the results; open index.html from there")


class Repo:
    reponame: str


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel(pargs.log)
    pd.options.display.max_rows = 250
    os.makedirs(pargs.outputdir, exist_ok=True)
    pargs.startdate_dt = dt.datetime.fromisoformat(pargs.startdate).replace(tzinfo=dt.timezone.utc)
    repodirs = pull_all_repos(not pargs.nopull)
    task_data = task_data_from_repos(repodirs)
    events = collect_events(repodirs)
    if not events:
        write_report_page(pargs.outputdir, [], pargs.startdate, 0, 0)
        b.warning("No events found. Wrote empty evaluator report.")
        return
    events_df = as_events_df(events, pargs.startdate_dt)
    weeks_df = weekly_studentsum(events_df)
    weekly_df = pd.DataFrame(fill_all_weeks(weeks_df))
    sections = []
    sections.append(plot_weekly_student_quantiles(
        weekly_df, 'accept', 'cumtimevalue', 'timevalue hours accepted',
        pargs.outputdir, "Accepted timevalue progression",
        "Shows how accepted timevalue accumulates by student over course weeks.",
        "Design idea: quartile stack plot highlights spread, not only central tendency. "
        "A tradeoff is visual density; a line-only variant can be cleaner but hides range."
    ))
    sections.append(plot_weekly_student_quantiles(
        weekly_df, 'reject', 'cumtimevalue', 'timevalue hours rejected',
        pargs.outputdir, "Rejected timevalue progression",
        "Shows how much timevalue was spent on rejected submissions over time.",
        "Design idea: keeping this structurally identical to the accepted plot allows "
        "direct comparison. Variant: normalized percentages instead of absolute hours."
    ))
    sections.append(plot_weekly_student_quantiles(
        weekly_df, 'work', 'cumtimevalue', 'hours worked',
        pargs.outputdir, "Worktime progression",
        "Shows cumulative worked hours per student and week from worktime commits.",
        "Design idea: the same quartile format supports quick cross-reading of all three "
        "time-series dimensions. Variant: split by chapter stage if stage metadata is available."
    ))
    sections.append(plot_weekly_event_counts(
        events_df, pargs.outputdir,
        "Weekly submission/check activity",
        "Shows total count of work/accept/reject events per week across the cohort.",
        "Design idea: absolute weekly intensity exposes pressure peaks around deadlines. "
        "Variant: smooth trend lines can reduce noise but can hide short spikes."
    ))
    sections.append(plot_top_tasks(
        events_df, pargs.outputdir,
        "Most worked-on tasks",
        "Shows tasks with the highest number of work commits and checked submissions.",
        "Design idea: side-by-side bar variants reveal popularity from two angles. "
        "Tradeoff: counts ignore time spent; add weighted bars when needed."
    ))
    sections.append(plot_task_effort_ratio(
        events_df, task_data, pargs.outputdir,
        "Task effort ratio (worked vs. nominal timevalue)",
        "Shows which tasks consume much more or less work than their nominal timevalue.",
        "Design idea: ratio bars quickly flag candidates for recalibration. Variant: per-student "
        "boxplots better show spread but are heavier to read for many tasks."
    ))
    sections.append(plot_rejection_patterns(
        events_df, pargs.outputdir,
        "Rejection patterns by task and student",
        "Shows where rejections cluster in tasks and among students.",
        "Design idea: two compact top-N views separate task quality signals from "
        "individual support signals. Variant: heatmaps provide full detail with higher visual load."
    ))
    sections.append(plot_instructor_load(
        events_df, pargs.outputdir,
        "Instructor checking load",
        "Shows how accept/reject checks are distributed among instructor committers.",
        "Design idea: stacked bars reveal both total load and rejection share per instructor. "
        "Variant: percentages-only bars improve comparability but hide absolute workload."
    ))
    sections.append(plot_taskgroup_start_order(
        events_df, task_data, pargs.outputdir,
        "Typical taskgroup start order",
        "Shows taskgroups ordered by the median week when students first touched them.",
        "Design idea: first-touch medians approximate navigation order through the course. "
        "Tradeoff: ignores revisits; a transition graph variant captures path dynamics."
    ))
    write_report_page(pargs.outputdir, sections, pargs.startdate,
                      len(events_df.student.unique()), len(events_df))


def pull_all_repos(do_pull: bool) -> list[str]:
    """Visit subdirs, pull repo in each (if any), return subdir names with a student.yaml."""
    repodir_list = []
    # ----- find repolist:
    for path in sorted(glob.glob("*")):
        if not os.path.isdir(path):
            continue  # skip files and potential exotic stuff
        if not os.path.isdir(os.path.join(path, '.git')):
            continue  # skip directories not containing a repo
        repodir_list.append(path)
    repodir_list.sort()
    # ----- pull each repo:
    if do_pull:
        b.info(f"pulling {len(repodir_list)} git repos")
        progressbar = b.get_progressbar(len(repodir_list))
        if os.path.isfile(c.EVENTCACHE_FILENAME):
            os.remove(c.EVENTCACHE_FILENAME)  # cache would be invalid after pull
    result = []
    for repodir in repodir_list:
        with contextlib.chdir(repodir):
            if do_pull:
                sgit.pull(silent=True)
                next(progressbar)
            if os.path.isfile(c.PARTICIPANT_FILE):  # skip repos without a declared identity
                result.append(repodir)
    return result


def collect_events(repodirs: list[str]) -> list[repo.Event]:
    """Visit subdirs, collect repo.event_list in each, cache result. Or return result from cache."""
    # ----- use data from cache:
    if os.path.isfile(c.EVENTCACHE_FILENAME):
        with open(c.EVENTCACHE_FILENAME, 'rb') as f:
            result = pickle.load(f)
        return result
    # ----- compute data and write it to cache:
    result = []
    numcommits = []
    b.info(f"collecting events in {len(repodirs)} student workdirs")
    progressbar = b.get_progressbar(len(repodirs))
    for repodir in repodirs:
        student_username = os.path.basename(repodir)
        with contextlib.chdir(repodir):
            student = sdrl.participant.Student('.', is_instructor=False)
            course_json = student.get_course_metadata(student.course_url)
            course = sdrl.course.CourseSI(course_json, student_username)
            commits = sgit.commits_of_local_repo(chronological=True)
            this_batch = repo.event_list(course, student_username, commits)
            result.extend(this_batch)
            numcommits.append(len(this_batch))
        next(progressbar)
    quantiles = pd.Series(numcommits).quantile([0, 0.25, 0.5, 0.75, 1.0])
    print("Quantiles of #commits over repos:\n", quantiles)
    with open(c.EVENTCACHE_FILENAME, 'wb') as f:
        pickle.dump(result, f)
    print(len(result), "events found")
    return result


def as_events_df(events: list[repo.Event], startdate: dt.datetime) -> pandas.DataFrame:
    def get_week(when) -> int:
        return int((when - startdate).total_seconds() / (7*24*3600))

    df = pd.DataFrame(events)
    df['week'] = df['when'].apply(get_week)
    df['date'] = df['when'].dt.date
    return df


def weekly_studentsum(events_df: pd.DataFrame) -> pd.DataFrame:
    grouped = events_df.groupby(['evtype', 'student', 'week'], as_index=False)
    weekly = grouped.agg(
        # when_from=('when', 'min'),
        # when_to=('when', 'max'),
        timevalue=('timevalue', 'sum')
    )
    grouped = weekly.groupby(['evtype', 'student'], as_index=False)
    weekly['cumtimevalue'] = grouped['timevalue'].cumsum()
    return weekly


def fill_all_weeks(weeks_df: pd.DataFrame):
    """
    Generator for adding rows for weeks for which there is none. 
    Relies on and extends existing ordering: increasing evtype, then student, then week.
    """
    # There has to be a simpler solution than this:
    def fill_one_gap(endweek: int, lastrow: pd.Series):
        for week in range(lastrow.week + 1, endweek+1):
            newrow = lastrow.copy()
            newrow.week = week
            # newrow.when_from = newrow.when_to = None
            newrow.timevalue = 0.0
            yield newrow
            lastrow = newrow
        return lastrow

    lastrow = None
    max_week = weeks_df.week.max()
    for idx, row in weeks_df.iterrows():
        still_in_same_group = (lastrow is not None and 
                               (row.evtype, row.student) == (lastrow.evtype, lastrow.student))
        if still_in_same_group:  # continue present group
            if row.week > lastrow.week + 1:
                yield from fill_one_gap(row.week-1, lastrow)
        else:  # start new group
            if lastrow is not None and lastrow.week < max_week:
                yield from fill_one_gap(max_week, lastrow)
        yield row
        lastrow = row


def plot_weekly_student_quantiles(weekly_df: pd.DataFrame, evtype: str, attrname: str, ylabel: str,
                                  outputdir: str, title: str, explanation: str,
                                  design_notes: str) -> dict[str, tg.Any]:
    def qt(quantile: float) -> tg.Callable[[pd.Series], float]:
        def myqt(series) -> float:
            return pd.Series.quantile(series, quantile)
        return myqt

    events = weekly_df[weekly_df.evtype == evtype].groupby('week', as_index=False)
    quantiles = events.agg(
        week=('week', 'first'),
        q0=(attrname, qt(0.0)),  # min
        q1=(attrname, qt(0.25)),
        q2=(attrname, qt(0.5)),  # median
        q3=(attrname, qt(0.75)),
        q4=(attrname, qt(1.0)),  # max 
    )
    plt.figure(figsize=(7.0, 3.5))
    plt.title(title)
    plt.grid(axis='y', linewidth=0.1)
    for column, color in [('q4','darkgreen'), ('q3', 'gold'), ('q2', 'orange'), ('q1', 'tab:red'), ('q0', 'white')]:
        label = column.replace('q', 'Quarter ')
        plt.fill_between(quantiles.week, quantiles[column], color=color, label="" if '0' in label else label)
    plt.xlabel("week")
    plt.ylabel(ylabel)
    plt.legend(loc='upper left')
    plt.subplots_adjust(left=0.1, right=0.98, bottom=0.15, top=0.90)
    filename = f"stackplot-weekly-student-quantiles-{evtype}.png"
    plt.savefig(os.path.join(outputdir, filename), dpi=120)
    plt.close()
    return dict(
        slug=f"weekly-quantiles-{evtype}",
        title=title,
        images=[filename],
        explanation=explanation,
        design_notes=design_notes,
    )


def task_data_from_repos(repodirs: list[str]) -> dict[str, dict[str, tg.Any]]:
    if not repodirs:
        return {}
    with contextlib.chdir(repodirs[0]):
        student = sdrl.participant.Student('.', is_instructor=False)
        course_json = student.get_course_metadata(student.course_url)
        course = sdrl.course.CourseSI(course_json, os.path.basename(repodirs[0]))
    return {
        taskname: dict(path=task.path, timevalue=task.timevalue, difficulty=task.difficulty)
        for taskname, task in course.taskdict.items()
    }


def plot_weekly_event_counts(events_df: pd.DataFrame, outputdir: str, title: str,
                             explanation: str, design_notes: str) -> dict[str, tg.Any]:
    weekly_counts = (events_df.groupby(['week', 'evtype'], as_index=False)
                     .size()
                     .rename(columns=dict(size='events')))
    pivot = weekly_counts.pivot(index='week', columns='evtype', values='events').fillna(0.0)
    plt.figure(figsize=(7.0, 3.5))
    pivot.plot(ax=plt.gca(), kind='bar', stacked=True,
               color=dict(work='tab:blue', accept='tab:green', reject='tab:red'))
    plt.title(title)
    plt.xlabel("week")
    plt.ylabel("number of events")
    plt.subplots_adjust(left=0.09, right=0.99, bottom=0.24, top=0.90)
    filename = "bars-weekly-event-counts.png"
    plt.savefig(os.path.join(outputdir, filename), dpi=120)
    plt.close()
    return dict(slug='weekly-event-counts', title=title, images=[filename],
                explanation=explanation, design_notes=design_notes)


def plot_top_tasks(events_df: pd.DataFrame, outputdir: str, title: str, explanation: str,
                   design_notes: str) -> dict[str, tg.Any]:
    top_work = (events_df[events_df.evtype == 'work'].groupby('taskname').size()
                .sort_values(ascending=False).head(15))
    top_checks = (events_df[events_df.evtype != 'work'].groupby('taskname').size()
                  .sort_values(ascending=False).head(15))
    filenames = []
    if len(top_work):
        plt.figure(figsize=(8.0, 3.8))
        top_work.sort_values().plot(kind='barh', color='tab:blue')
        plt.title("Top tasks by work commit count")
        plt.xlabel("work commits")
        plt.ylabel("task")
        plt.subplots_adjust(left=0.26, right=0.98, bottom=0.12, top=0.88)
        filename = "bars-top-tasks-work.png"
        plt.savefig(os.path.join(outputdir, filename), dpi=120)
        plt.close()
        filenames.append(filename)
    if len(top_checks):
        plt.figure(figsize=(8.0, 3.8))
        top_checks.sort_values().plot(kind='barh', color='tab:purple')
        plt.title("Top tasks by checked submission count")
        plt.xlabel("accept/reject checks")
        plt.ylabel("task")
        plt.subplots_adjust(left=0.26, right=0.98, bottom=0.12, top=0.88)
        filename = "bars-top-tasks-checks.png"
        plt.savefig(os.path.join(outputdir, filename), dpi=120)
        plt.close()
        filenames.append(filename)
    return dict(slug='top-tasks', title=title, images=filenames,
                explanation=explanation, design_notes=design_notes)


def plot_task_effort_ratio(events_df: pd.DataFrame, task_data: dict[str, dict[str, tg.Any]],
                           outputdir: str, title: str, explanation: str,
                           design_notes: str) -> dict[str, tg.Any]:
    if not task_data:
        return dict(slug='task-effort-ratio', title=title, images=[],
                    explanation=explanation, design_notes=design_notes)
    worktime = (events_df[events_df.evtype == 'work'].groupby('taskname')['timevalue']
                .sum().rename('worked_hours'))
    nominal = pd.Series({k: v['timevalue'] for k, v in task_data.items()}, name='nominal_hours')
    ratio = (pd.concat([worktime, nominal], axis=1)
             .fillna(0.0)
             .assign(ratio=lambda df: df['worked_hours'] / df['nominal_hours'].replace(0, pd.NA)))
    ratio = ratio.dropna().sort_values('ratio', ascending=False).head(15).sort_values('ratio')
    if not len(ratio):
        return dict(slug='task-effort-ratio', title=title, images=[],
                    explanation=explanation, design_notes=design_notes)
    plt.figure(figsize=(8.0, 3.8))
    plt.barh(ratio.index, ratio['ratio'], color='tab:orange')
    plt.axvline(1.0, color='black', linewidth=0.8, linestyle='--')
    plt.title(title)
    plt.xlabel("worked hours / nominal timevalue")
    plt.ylabel("task")
    plt.subplots_adjust(left=0.26, right=0.98, bottom=0.12, top=0.88)
    filename = "bars-task-effort-ratio.png"
    plt.savefig(os.path.join(outputdir, filename), dpi=120)
    plt.close()
    return dict(slug='task-effort-ratio', title=title, images=[filename],
                explanation=explanation, design_notes=design_notes)


def plot_rejection_patterns(events_df: pd.DataFrame, outputdir: str, title: str,
                            explanation: str, design_notes: str) -> dict[str, tg.Any]:
    rejects = events_df[events_df.evtype == 'reject']
    filenames = []
    by_task = rejects.groupby('taskname').size().sort_values(ascending=False).head(15)
    if len(by_task):
        plt.figure(figsize=(8.0, 3.8))
        by_task.sort_values().plot(kind='barh', color='tab:red')
        plt.title("Top tasks by rejection count")
        plt.xlabel("rejections")
        plt.ylabel("task")
        plt.subplots_adjust(left=0.26, right=0.98, bottom=0.12, top=0.88)
        filename = "bars-rejections-by-task.png"
        plt.savefig(os.path.join(outputdir, filename), dpi=120)
        plt.close()
        filenames.append(filename)
    by_student = rejects.groupby('student').size().sort_values(ascending=False).head(15)
    if len(by_student):
        plt.figure(figsize=(8.0, 3.8))
        by_student.sort_values().plot(kind='barh', color='firebrick')
        plt.title("Top students by rejection count")
        plt.xlabel("rejections")
        plt.ylabel("student")
        plt.subplots_adjust(left=0.20, right=0.98, bottom=0.12, top=0.88)
        filename = "bars-rejections-by-student.png"
        plt.savefig(os.path.join(outputdir, filename), dpi=120)
        plt.close()
        filenames.append(filename)
    return dict(slug='rejection-patterns', title=title, images=filenames,
                explanation=explanation, design_notes=design_notes)


def plot_instructor_load(events_df: pd.DataFrame, outputdir: str, title: str, explanation: str,
                         design_notes: str) -> dict[str, tg.Any]:
    checks = events_df[events_df.evtype != 'work']
    dist = (checks.groupby(['committer', 'evtype'], as_index=False)
            .size().rename(columns=dict(size='checks')))
    if not len(dist):
        return dict(slug='instructor-load', title=title, images=[],
                    explanation=explanation, design_notes=design_notes)
    pivot = dist.pivot(index='committer', columns='evtype', values='checks').fillna(0.0)
    plt.figure(figsize=(8.0, 3.8))
    pivot.plot(ax=plt.gca(), kind='bar', stacked=True,
               color=dict(accept='tab:green', reject='tab:red'))
    plt.title(title)
    plt.xlabel("committer")
    plt.ylabel("checks")
    plt.xticks(rotation=35, ha='right')
    plt.subplots_adjust(left=0.10, right=0.98, bottom=0.33, top=0.88)
    filename = "bars-instructor-load.png"
    plt.savefig(os.path.join(outputdir, filename), dpi=120)
    plt.close()
    return dict(slug='instructor-load', title=title, images=[filename],
                explanation=explanation, design_notes=design_notes)


def plot_taskgroup_start_order(events_df: pd.DataFrame, task_data: dict[str, dict[str, tg.Any]],
                               outputdir: str, title: str, explanation: str,
                               design_notes: str) -> dict[str, tg.Any]:
    def taskgroup_of(taskname: str) -> str:
        path = task_data.get(taskname, {}).get('path', "")
        parts = path.split('/')
        return '/'.join(parts[:2]) if len(parts) >= 2 else "unknown"

    first_touch = (events_df[events_df.evtype == 'work']
                   .assign(taskgroup=lambda df: df.taskname.apply(taskgroup_of))
                   .groupby(['student', 'taskgroup'], as_index=False)
                   .agg(first_week=('week', 'min')))
    if not len(first_touch):
        return dict(slug='taskgroup-order', title=title, images=[],
                    explanation=explanation, design_notes=design_notes)
    tg_order = (first_touch.groupby('taskgroup', as_index=False)
                .agg(median_week=('first_week', 'median'),
                     students=('student', 'nunique'))
                .query('students >= 3')
                .sort_values(['median_week', 'students'])
                .tail(20))
    if not len(tg_order):
        return dict(slug='taskgroup-order', title=title, images=[],
                    explanation=explanation, design_notes=design_notes)
    plt.figure(figsize=(8.5, 4.5))
    plt.barh(tg_order.taskgroup, tg_order.median_week, color='teal')
    plt.title(title)
    plt.xlabel("median first-touch week")
    plt.ylabel("taskgroup (chapter/taskgroup)")
    plt.subplots_adjust(left=0.30, right=0.98, bottom=0.10, top=0.88)
    filename = "bars-taskgroup-start-order.png"
    plt.savefig(os.path.join(outputdir, filename), dpi=120)
    plt.close()
    return dict(slug='taskgroup-order', title=title, images=[filename],
                explanation=explanation, design_notes=design_notes)


def write_report_page(outputdir: str, sections: list[dict[str, tg.Any]], startdate: str,
                      student_count: int, event_count: int):
    overview = "\n".join(
        f"<li><a href='#{html.escape(s['slug'])}'>{html.escape(s['title'])}</a></li>" for s in sections
    )
    body_sections = []
    for section in sections:
        images = "".join(
            f"<p><img src='{html.escape(img)}' alt='{html.escape(section['title'])}' "
            f"style='max-width: 100%; height: auto;'/></p>" for img in section.get('images', [])
        )
        body_sections.append(
            f"<section id='{html.escape(section['slug'])}'>"
            f"<h2>{html.escape(section['title'])}</h2>"
            f"{images}"
            f"<p>{html.escape(section['explanation'])}</p>"
            f"<p>{html.escape(section['design_notes'])}</p>"
            "</section>"
        )
    report_html = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'/>
  <title>SeDriLa evaluator report</title>
  <style>
    body {{ font-family: sans-serif; line-height: 1.4; margin: 2rem auto; max-width: 1000px; }}
    img {{ border: 1px solid #ddd; padding: 0.2rem; background: #fff; }}
    section {{ margin: 2.2rem 0; }}
  </style>
</head>
<body>
  <h1>SeDriLa cohort evaluator report</h1>
  <p>Start date: {html.escape(startdate)} | Students: {student_count} | Events: {event_count}</p>
  <h2>Overview</h2>
  <ul>{overview}</ul>
  {''.join(body_sections)}
</body>
</html>
"""
    with open(os.path.join(outputdir, "index.html"), 'w', encoding='utf8') as f:
        f.write(report_html)
