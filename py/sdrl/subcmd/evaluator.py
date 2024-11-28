"""
Statistical evaluation (by a course organizer/course developer) of the progress of 
an entire course cohort.

Goals:
- Understand difficulty level distribution across the students.
- Identify tasks with too-low or too-high time value (via worktime) or difficulty (via resubmissions).
- Understand re-submission behavior patterns (per people, per tasks, over time).
- Understand work time patterns (workdays, weekly trends, etc.)
"""
import contextlib
import datetime as dt
import functools
import glob
import os
import pickle
import typing as tg

import argparse_subcommand as ap_sub
import matplotlib.pyplot as plt
import pandas
import pandas as pd

import base as b
import git
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
    pargs.startdate_dt = dt.datetime.fromisoformat(pargs.startdate).replace(tzinfo=dt.timezone.utc) 
    repodirs = pull_all_repos(not pargs.nopull)
    events = collect_events(repodirs)
    events_df = as_events_df(events, pargs.startdate_dt)
    # events_df.info(buf=sys.stdout)
    weeks_df = weekly_studentsum(events_df)
    weekly_df = pd.DataFrame(fill_all_weeks(weeks_df))
    # print(weekly_df.query('evtype == "work"'))
    plot_weekly_student_quantiles(weekly_df, 'accept', 'cumtimevalue', 
                                  'timevalue hours accepted', pargs.outputdir)
    plot_weekly_student_quantiles(weekly_df, 'reject', 'cumtimevalue', 
                                  'timevalue hours rejected', pargs.outputdir)
    plot_weekly_student_quantiles(weekly_df, 'work', 'cumtimevalue', 
                                  'hours worked', pargs.outputdir)


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
        os.remove(c.EVENTCACHE_FILENAME)  # cache would be invalid after pull
    result = []
    for repodir in repodir_list:
        with contextlib.chdir(repodir):
            if do_pull:
                git.pull(silent=True)
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
            student = sdrl.participant.Student()
            course_json = student.get_metadata(student.course_url)
            course = sdrl.course.CourseSI(course_json, student_username)
            commits = git.commits_of_local_repo()
            this_batch = repo.event_list(course, student_username, commits)
            result.extend(this_batch)
            numcommits.append(len(this_batch))
        next(progressbar)
    quantiles = pd.Series(numcommits).quantile([0, 0.25, 0.5, 0.75, 1.0])
    print("Quantiles of #commits:\n", quantiles)
    with open(c.EVENTCACHE_FILENAME, 'wb') as f:
        pickle.dump(result, f)
    print(len(result), "events found")
    return result


def as_events_df(events: list[repo.Event], startdate: dt.datetime) -> pandas.DataFrame:
    def get_week(when) -> int:
        return int((when - startdate).total_seconds() / (7*24*3600))

    df = pd.DataFrame(events)
    df['week'] = df['when'].apply(get_week)
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


def plot_weekly_student_quantiles(weekly_df: pd.DataFrame, evtype: str, attrname: str,
                                  ylabel: str, outputdir: str):
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
    plt.figure(figsize=(6.0, 3.0))
    plt.grid(axis='y', linewidth=0.1)
    for column, color in [('q4','darkgreen'), ('q3', 'gold'), ('q2', 'orange'), ('q1', 'tab:red'), ('q0', 'white')]:
        label = column.replace('q', 'Quarter ')
        plt.fill_between(quantiles.week, quantiles[column], color=color, label="" if '0' in label else label)
    plt.xlabel("week")
    plt.ylabel(ylabel)
    plt.legend(loc='upper left')
    plt.subplots_adjust(left=0.1, right=0.98, bottom=0.15, top=0.98)
    plt.savefig(os.path.join(outputdir, f"stackplot-weekly-student-quantiles-{evtype}.pdf"))

