# pytest tests for bonus/anti-procrastination logic.

import datetime as dt
import unittest.mock

import pytest

import base as b
import sdrl.course
import sdrl.course_si


# ----- helpers -----

MINIMAL_CONFIGDICT = dict(
    title='Test Course', name='test',
    instructors=[dict(nameish='Test', email='test@t.de',
                      gitaccount='t', webaccount='t',
                      keyfingerprint='A' * 40, pubkey='pk')],
    allowed_attempts='2',
    chapters=[],
)


def make_course_si(startdate: str, enddate: str, bonusrules: dict | None = None) -> sdrl.course_si.CourseSI:
    """Create a minimal CourseSI for testing; bypass normal chapter/task loading."""
    configdict = dict(MINIMAL_CONFIGDICT)
    configdict['startdate'] = startdate
    configdict['enddate'] = enddate
    if bonusrules:
        configdict['bonusrules'] = bonusrules
    course = sdrl.course_si.CourseSI(configdict=configdict, context='test')
    return course


def make_task(accept_date: dt.datetime | None, timevalue: float = 1.0) -> sdrl.course.Task:
    """Create a minimal mock Task."""
    task = unittest.mock.MagicMock(spec=sdrl.course.Task)
    task.accept_date = accept_date
    task.timevalue = timevalue
    return task


# ----- Task.is_accepted property -----

def test_task_is_accepted_none():
    """Task with accept_date=None is not accepted."""
    task = sdrl.course.Task.__new__(sdrl.course.Task)
    task.accept_date = None
    assert not task.is_accepted


def test_task_is_accepted_with_date():
    """Task with an accept_date is accepted."""
    task = sdrl.course.Task.__new__(sdrl.course.Task)
    task.accept_date = dt.datetime(2025, 5, 15, 12, 0, 0)
    assert task.is_accepted


# ----- bonus_period_ranges: month type -----

def test_bonus_period_ranges_month_simple():
    """3 monthly periods starting 2025-04-15."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=3, bonus_threshold_percent=10, bonus_size_percent=2)
    course = make_course_si('2025-04-15', '2026-03-31', bonusrules)
    ranges = course.bonus_period_ranges()
    assert len(ranges) == 3
    # Period 1: 2025-04-15 to 2025-04-30
    assert ranges[0] == (dt.date(2025, 4, 15), dt.date(2025, 4, 30))
    # Period 2: 2025-05-01 to 2025-05-31
    assert ranges[1] == (dt.date(2025, 5, 1), dt.date(2025, 5, 31))
    # Period 3: 2025-06-01 to 2025-06-30
    assert ranges[2] == (dt.date(2025, 6, 1), dt.date(2025, 6, 30))


def test_bonus_period_ranges_month_year_boundary():
    """Periods crossing year boundary."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=3, bonus_threshold_percent=10, bonus_size_percent=2)
    course = make_course_si('2025-11-01', '2026-03-31', bonusrules)
    ranges = course.bonus_period_ranges()
    assert len(ranges) == 3
    assert ranges[0] == (dt.date(2025, 11, 1), dt.date(2025, 11, 30))
    assert ranges[1] == (dt.date(2025, 12, 1), dt.date(2025, 12, 31))
    assert ranges[2] == (dt.date(2026, 1, 1), dt.date(2026, 1, 31))


# ----- bonus_period_ranges: week type -----

def test_bonus_period_ranges_week_simple():
    """3 weekly periods starting on a Wednesday (2025-04-16 is a Wednesday)."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='week',
                      bonusperiods=3, bonus_threshold_percent=10, bonus_size_percent=2)
    course = make_course_si('2025-04-16', '2026-03-31', bonusrules)
    ranges = course.bonus_period_ranges()
    assert len(ranges) == 3
    # Period 1: Wed 2025-04-16 to Sun 2025-04-20
    assert ranges[0] == (dt.date(2025, 4, 16), dt.date(2025, 4, 20))
    # Period 2: Mon 2025-04-21 to Sun 2025-04-27
    assert ranges[1] == (dt.date(2025, 4, 21), dt.date(2025, 4, 27))
    # Period 3: Mon 2025-04-28 to Sun 2025-05-04
    assert ranges[2] == (dt.date(2025, 4, 28), dt.date(2025, 5, 4))


def test_bonus_period_ranges_week_starts_on_monday():
    """Periods starting on a Monday (full first week)."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='week',
                      bonusperiods=2, bonus_threshold_percent=10, bonus_size_percent=2)
    course = make_course_si('2025-04-14', '2026-03-31', bonusrules)  # Monday
    ranges = course.bonus_period_ranges()
    assert len(ranges) == 2
    assert ranges[0] == (dt.date(2025, 4, 14), dt.date(2025, 4, 20))
    assert ranges[1] == (dt.date(2025, 4, 21), dt.date(2025, 4, 27))


# ----- compute_bonus -----

def test_compute_bonus_period_criterion():
    """Period criterion: enough work in a single period triggers bonus."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=2, bonus_threshold_percent=11, bonus_size_percent=2)
    course = make_course_si('2025-04-15', '2026-03-31', bonusrules)
    # course_size_hours = 100; threshold = 11h per period for bonus
    # task accepted 2025-04-20: 12h → period 1 criterion met (12 >= 11)
    task = make_task(dt.datetime(2025, 4, 20, 12, 0, 0), timevalue=12.0)
    course._Course__taskdict_cache = None  # clear cached property if any
    with unittest.mock.patch.object(type(course), 'taskdict', new_callable=unittest.mock.PropertyMock) as mock_td:
        mock_td.return_value = {'T1': task}
        results = course.compute_bonus(100.0)
    assert len(results) == 2
    assert results[0].bonus_hours == pytest.approx(2.0)  # 2% of 100
    assert results[1].bonus_hours == 0.0  # no work in period 2


def test_compute_bonus_cumulative_criterion():
    """Cumulative criterion: enough work over multiple periods triggers period 2 bonus."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=2, bonus_threshold_percent=11, bonus_size_percent=2)
    course = make_course_si('2025-04-15', '2026-03-31', bonusrules)
    # 8h in period 1 (not enough for period criterion 11h),
    # then 14h in period 2 → cumulative = 22h >= 11*2 = 22h → cumulative criterion met
    task1 = make_task(dt.datetime(2025, 4, 20, 12, 0, 0), timevalue=8.0)
    task2 = make_task(dt.datetime(2025, 5, 10, 12, 0, 0), timevalue=14.0)
    with unittest.mock.patch.object(type(course), 'taskdict', new_callable=unittest.mock.PropertyMock) as mock_td:
        mock_td.return_value = {'T1': task1, 'T2': task2}
        results = course.compute_bonus(100.0)
    assert results[0].bonus_hours == 0.0  # 8 < 11, cumulative 8 < 11*1=11
    assert results[1].bonus_hours == pytest.approx(2.0)  # cumulative 22 >= 11*2=22


def test_compute_bonus_neither_criterion():
    """Neither criterion met: no bonus."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=2, bonus_threshold_percent=11, bonus_size_percent=2)
    course = make_course_si('2025-04-15', '2026-03-31', bonusrules)
    task1 = make_task(dt.datetime(2025, 4, 20, 12, 0, 0), timevalue=5.0)
    task2 = make_task(dt.datetime(2025, 5, 10, 12, 0, 0), timevalue=5.0)
    with unittest.mock.patch.object(type(course), 'taskdict', new_callable=unittest.mock.PropertyMock) as mock_td:
        mock_td.return_value = {'T1': task1, 'T2': task2}
        results = course.compute_bonus(100.0)
    assert results[0].bonus_hours == 0.0
    assert results[1].bonus_hours == 0.0


def test_compute_bonus_unaccepted_tasks_ignored():
    """Tasks with accept_date=None (not accepted) are ignored."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=1, bonus_threshold_percent=11, bonus_size_percent=2)
    course = make_course_si('2025-04-15', '2026-03-31', bonusrules)
    task_accepted = make_task(dt.datetime(2025, 4, 20, 12, 0, 0), timevalue=20.0)
    task_rejected = make_task(None, timevalue=50.0)
    with unittest.mock.patch.object(type(course), 'taskdict', new_callable=unittest.mock.PropertyMock) as mock_td:
        mock_td.return_value = {'T1': task_accepted, 'T2': task_rejected}
        results = course.compute_bonus(100.0)
    assert results[0].period_hours == pytest.approx(20.0)
    assert results[0].bonus_hours == pytest.approx(2.0)


def test_total_bonus():
    """total_bonus sums bonus_hours correctly."""
    results = [
        sdrl.course_si.BonusPeriodResult(1, 'A', 10, 10, 10, 10, 2.0),
        sdrl.course_si.BonusPeriodResult(2, 'B', 5, 5, 15, 15, 0.0),
        sdrl.course_si.BonusPeriodResult(3, 'C', 12, 12, 27, 27, 2.0),
    ]
    assert sdrl.course_si.CourseSI.total_bonus(results) == pytest.approx(4.0)


# ----- _validate_bonusrules errors -----

def test_validate_bonusrules_startdate_after_enddate():
    """startdate >= enddate must raise a critical error."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=3, bonus_threshold_percent=11, bonus_size_percent=2)
    with pytest.raises(b.CritialError):
        make_course_si('2026-01-01', '2025-01-01', bonusrules)


def test_validate_bonusrules_periods_times_threshold_over_100():
    """bonusperiods * bonus_threshold_percent > 100 must raise a critical error."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=10, bonus_threshold_percent=11, bonus_size_percent=2)
    with pytest.raises(b.CritialError):
        make_course_si('2025-01-01', '2026-12-31', bonusrules)


def test_validate_bonusrules_not_enough_periods():
    """Too few periods in date range must raise a critical error."""
    bonusrules = dict(student_yaml_attribute='csz', bonusperiod_type='month',
                      bonusperiods=12, bonus_threshold_percent=8, bonus_size_percent=2)
    # Only 3 months from 2025-04-15 to 2026-03-31... wait that's 12 months.
    # Use a short date range: 2025-04-15 to 2025-05-31 = 2 months, but bonusperiods=3
    with pytest.raises(b.CritialError):
        make_course_si('2025-04-15', '2025-05-31', bonusrules)
