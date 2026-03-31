"""
CourseSI: Course subclass for student and instructor subcommands.
"""
import calendar
import dataclasses
import datetime as dt
import typing as tg

import base as b
import sdrl.course
from sdrl.course import Course, Chapter, Taskgroup, Task


@dataclasses.dataclass
class BonusPeriodResult:
    period_num: int           # 1-based
    label: str                # "April 2025" or "2025-04-20" (week end date)
    period_hours: float       # timevalue earned in this period
    period_percent: float     # period_hours as % of course_size_hours
    cumulative_hours: float   # total earned up to end of this period
    cumulative_percent: float # cumulative_hours as % of course_size_hours
    bonus_hours: float        # bonus for this period (0 if criterion not met)


class CourseSI(Course):
    """Course for cmds student and instructor. Init from c.METADATA_FILE."""
    MUSTCOPY_ADDITIONAL = ''
    CANCOPY_ADDITIONAL = ''

    chapters: list['Chapter']
    manual_bookings: list  # list[repo.ManualEntry], populated by compute_student_work_so_far
    manual_timevalue: float  # sum of all manual bookings

    def __init__(self, configdict: b.StrAnyDict, context: str):
        super().__init__(configdict=configdict, context=context)
        self.manual_bookings = []
        self.manual_timevalue = 0.0
        self.parttype = dict(Chapter=Chapter, Taskgroup=Taskgroup, Task=Task)
        self._init_parts(self.configdict)

    def _init_parts(self, configdict: dict):
        self.chapters = [Chapter(ch['name'], parent=self, chapterdict=ch)  # noqa
                         for ch in configdict['chapters']]

    def bonus_period_ranges(self) -> list[tuple[dt.date, dt.date]]:
        """Return (start, end) date pairs for each eligible bonus period."""
        br = self.bonusrules
        assert br is not None and self.startdate is not None
        n = br['bonusperiods']
        period_type = br['bonusperiod_type']
        ranges = []
        if period_type == 'month':
            year, month = self.startdate.year, self.startdate.month
            for i in range(n):
                start = self.startdate if i == 0 else dt.date(year, month, 1)
                last_day = calendar.monthrange(year, month)[1]
                end = dt.date(year, month, last_day)
                ranges.append((start, end))
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:  # week
            # period 1 starts at startdate, ends at Sunday of that ISO week
            start = self.startdate
            for i in range(n):
                # Sunday of the week containing start
                days_until_sunday = 6 - start.weekday()  # weekday(): Mon=0 ... Sun=6
                end = start + dt.timedelta(days=days_until_sunday)
                ranges.append((start, end))
                start = end + dt.timedelta(days=1)  # next Monday
        return ranges

    def bonus_period_label(self, start: dt.date, end: dt.date) -> str:
        """Return display label for a bonus period."""
        br = self.bonusrules
        assert br is not None
        if br['bonusperiod_type'] == 'month':
            return start.strftime("%B %Y")
        else:
            return end.strftime("%Y-%m-%d")

    def compute_bonus(self, course_size_hours: float) -> list[BonusPeriodResult]:
        """Compute bonus results for each eligible period for this student."""
        br = self.bonusrules
        assert br is not None
        threshold = br['bonus_threshold_percent'] / 100.0
        bonus_size = br['bonus_size_percent'] / 100.0
        ranges = self.bonus_period_ranges()
        results = []
        cumulative_hours = 0.0
        for p_idx, (period_start, period_end) in enumerate(ranges):
            p_num = p_idx + 1
            period_hours = sum(
                task.timevalue
                for task in self.taskdict.values()
                if task.accept_date is not None
                and period_start <= task.accept_date.date() <= period_end
            )
            cumulative_hours += period_hours
            period_percent = (period_hours / course_size_hours * 100.0) if course_size_hours else 0.0
            cumulative_percent = (cumulative_hours / course_size_hours * 100.0) if course_size_hours else 0.0
            # Bonus criteria: period or cumulative average meets threshold
            period_criterion = period_hours >= course_size_hours * threshold
            cumulative_criterion = cumulative_hours >= course_size_hours * p_num * threshold
            bonus = (course_size_hours * bonus_size) if (period_criterion or cumulative_criterion) else 0.0
            label = self.bonus_period_label(period_start, period_end)
            results.append(BonusPeriodResult(
                period_num=p_num,
                label=label,
                period_hours=period_hours,
                period_percent=period_percent,
                cumulative_hours=cumulative_hours,
                cumulative_percent=cumulative_percent,
                bonus_hours=bonus,
            ))
        return results

    @staticmethod
    def total_bonus(results: list[BonusPeriodResult]) -> float:
        """Sum of bonus_hours across all period results."""
        return sum(r.bonus_hours for r in results)
