"""
Represent and handle the contents of SeDriLa: Course, Chapter, Taskgroup, Task.
There are two ways how these objects can be instantiated:
In 'author' mode, metadata comes from sedrila.yaml and the partfiles.
Otherwise, metadata comes from METADATA_FILE.
"""
import datetime as dt
import functools
import os
import re
import typing as tg

import base as b
import sdrl.constants as c
import sdrl.elements as el
import sdrl.html as h


class Task(el.Part):
    DIFFICULTY_RANGE = range(1, len(h.difficulty_levels) + 1)
    TOC_LEVEL = 2  # indent level in table of contents

    course: 'Course'
    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: int  # difficulty: int from DIFFICULTY_RANGE
    assumes: list[str] = []  # tasknames: This knowledge is assumed to be present
    requires: list[str] = []  # tasknames: These specific results will be reused here
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    accept_date: dt.datetime | None = None  # date of last accept event, set in repo.py
    rejections: int = 0  # how often instructor has marked it 'reject'
    manual_timevalue: float = 0.0  # sum of task-specific manual bookings for this task

    @property
    def is_accepted(self) -> bool:
        return self.accept_date is not None

    taskgroup: 'Taskgroup'  # where the task belongs

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.course.namespace_add(self)

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def acceptance_state(self) -> str:
        if self.is_accepted:  # acceptance trumps possible rejection
            return c.SUBMISSION_ACCEPT_MARK
        elif self.remaining_attempts <= 0:
            return c.SUBMISSION_REJECT_MARK
        elif self.rejections > 0:
            return c.SUBMISSION_REJECTOID_MARK
        else:
            return c.SUBMISSION_NONCHECK_MARK

    @property
    def allowed_attempts(self) -> int:
        course = self.taskgroup.chapter.course
        return int(course.allowed_attempts_base + course.allowed_attempts_hourly*self.timevalue)

    @property
    def path(self) -> str:
        """Returns 'mychapter/mytaskgroup/self.name'"""
        return f"{self.taskgroup.chapter.name}/{self.taskgroup.name}/{self.name}"

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.allowed_attempts - self.rejections)

    @property
    def sourcefile(self) -> str:
        return f"{self.course.chapterdir}/{self.taskgroup.chapter.name}/{self.taskgroup.name}/{self.name}.md"

    @property
    def time_earned(self) -> float:
        return self.timevalue if self.is_accepted else 0.0

    def from_json(self, task: b.StrAnyDict) -> 'Task':
        """Initializer used in student and instructor mode. Ignores all additional attributes."""
        self.taskgroup = tg.cast('Taskgroup', self.parent)
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        return self


class Course(el.Part):
    """
    Abstract superclass for the master data object for this run. Can be instantiated in two different forms:
    - as Coursebuilder (for author):
      From a handwritten YAML file, called configfile.
      Will then read all content for a build and employ directory and cache.
    - as CourseSI (for student and instructor):
      From a JSON metadata file generated during build.
    The present superclass contains the attributes and logic that both have in common.
    """
    MUSTCOPY_ADDITIONAL = '???'  # set in subclasses
    CANCOPY_ADDITIONAL = '???'  # set in subclasses

    context: str  # for error messages: where config data comes from
    configdict: b.StrAnyDict  # all data from c.CONFIGFILE or c.METADATAFILE
    namespace: dict[str, el.Part]  # partname -> part, for obtaining Parts in any of the logic

    instructors: list[b.StrAnyDict]
    former_instructors: list[b.StrAnyDict]
    student_yaml_attribute_prompts: b.StrStrDict = dict()
    blockmacro_topmatter: b.StrStrDict = dict()
    allowed_attempts: str  # "2 + 0.5/h" or so, int+decimal, h is the task timevalue multiplier
    allowed_attempts_base: int  # the int part of allowed_attempts
    allowed_attempts_hourly: float  # the decimal part of allowed_attempts
    startdate: dt.date | None = None  # first day of the course
    enddate: dt.date | None = None  # last day of the course
    bonusrules: b.StrAnyDict | None = None  # bonus configuration dict, or None if no bonus

    def __init__(self, **kwargs):
        super().__init__("...", **kwargs)  # preliminary name!
        self.course = self
        self.namespace = dict()
        self._read_config(self.configdict)
        self.allowed_attempts_base, self.allowed_attempts_hourly = self._parse_allowed_attempts()

    @property
    def has_participantslist(self) -> bool:
        return 'participants' in self.configdict

    @functools.cached_property  # beware: call this only once initialization is complete!
    def taskdict(self) -> dict[str, 'Task']:
        return {k:v for k,v in self.namespace.items() if isinstance(v, Task)}

    def get_part(self, context: str, partname: str) -> el.Part:
        """Return part for given partname or self (and print error msg) if no such part exists."""
        if partname in self.namespace:
            return self.namespace[partname]
        b.error(f"part '{partname}' does not exist", file=context)
        return self

    def namespace_add(self, newpart: el.Part):
        name = newpart.name
        if name in self.namespace:
            b.critical("Files '%s' and '%s':\n   part name collision" %  # critical because it makes assumptions wrong
                       (self._partpath(self.namespace[name]), self._partpath(newpart)))
        else:
            self.namespace[name] = newpart

    def task(self, taskname: str):
        """Return Task for given taskname or None if no such task exists."""
        return self.taskdict.get(taskname, None)  # noqa

    def get_all_assumed_tasks(self, taskname: str) -> set[str]:
        """Recursively get all tasks that are assumed by a given task (transitive assumes closure)."""
        visited: set[str] = set()
        to_visit: list[str] = [taskname]
        while to_visit:
            current = to_visit.pop(0)
            task_obj = self.task(current)
            if task_obj is None or current in visited:
                continue
            visited.add(current)
            for assumed_task in task_obj.assumes:
                if assumed_task not in visited:
                    to_visit.append(assumed_task)
        visited.discard(taskname)
        return visited

    def _parse_allowed_attempts(self) -> tuple[int, float]:
        mm = re.match(r"(?P<base>\d+)(\s?\+\s?(?P<time>\d+\.\d+)\s?/\s?h)?", self.allowed_attempts)
        if not mm:
            msg1 = f"'allowed_attempts' must have a format exactly like '2 + 0.5/h' or '2'"
            b.error(f"{msg1}, not '{self.allowed_attempts}'", file=getattr(self, 'sourcefile', ''))
            return 2, 0
        return int(mm.group("base")), float(mm.group("time") or "0")

    @staticmethod
    def _partpath(p: el.Part) -> str:
        fullpath = p.sourcefile
        basename = os.path.basename(fullpath)
        dirname = os.path.dirname(fullpath)
        if basename == "index.md":
            return dirname
        else:
            return fullpath

    def _read_config(self, configdict: b.StrAnyDict):
        b.copyattrs(self.context,
                    configdict, self,
                    mustcopy_attrs=('title, name, instructors, allowed_attempts' +
                                    self.MUSTCOPY_ADDITIONAL),
                    cancopy_attrs=('participants, former_instructors, student_yaml_attribute_prompts,'
                                   'startdate, enddate, bonusrules' +
                                   self.CANCOPY_ADDITIONAL),
                    mustexist_attrs='chapters',
                    report_extra=bool(self.MUSTCOPY_ADDITIONAL))
        if self.former_instructors is None:
            self.former_instructors = []
        # Parse startdate/enddate strings into dt.date objects
        if isinstance(self.startdate, str):
            self.startdate = dt.date.fromisoformat(self.startdate)
        if isinstance(self.enddate, str):
            self.enddate = dt.date.fromisoformat(self.enddate)
        if self.bonusrules is not None:
            self._validate_bonusrules()


    def _validate_bonusrules(self):
        """Validate bonusrules config. Called only if bonusrules is not None."""
        br = self.bonusrules
        # Check startdate < enddate
        if self.startdate and self.enddate and self.startdate >= self.enddate:
            b.critical(f"bonusrules: 'startdate' ({self.startdate}) must be before 'enddate' ({self.enddate})")
        # Check bonusperiods * bonus_threshold_percent <= 100
        n = br.get('bonusperiods', 0)
        t = br.get('bonus_threshold_percent', 0)
        if n * t > 100:
            b.critical(f"bonusrules: bonusperiods ({n}) * bonus_threshold_percent ({t}) = {n*t} > 100")
        # Check enough periods in date range
        if self.startdate and self.enddate:
            period_type = br.get('bonusperiod_type', 'month')
            if period_type == 'month':
                total_periods = (self.enddate.year - self.startdate.year) * 12 + \
                                (self.enddate.month - self.startdate.month) + 1
            else:  # week
                start_monday = self.startdate - dt.timedelta(days=self.startdate.weekday())
                end_monday = self.enddate - dt.timedelta(days=self.enddate.weekday())
                total_periods = (end_monday - start_monday).days // 7 + 1
            if total_periods < n:
                b.critical(f"bonusrules: course has only {total_periods} {period_type}(s) "
                           f"but bonusperiods is {n}")
        # Check student_yaml_attribute is defined (only if prompts are set, i.e. in author mode)
        attr = br.get('student_yaml_attribute', '')
        if self.student_yaml_attribute_prompts and attr not in self.student_yaml_attribute_prompts:
            b.critical(f"bonusrules: student_yaml_attribute '{attr}' not in student_yaml_attribute_prompts")


class Chapter(el.Part):
    course: Course
    chapterdict: b.StrAnyDict
    taskgroups: list['Taskgroup']

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.course.namespace_add(self)
        context = f"chapter in {self.course.context}"
        self._init_from_dict(context, self.chapterdict)
        self._init_from_file(context, self.course)
        self.taskgroups = [self.parttype['Taskgroup'](taskgroup['name'],
                                                      parent=self, chapter=self,
                                                      taskgroupdict=taskgroup)
                           for taskgroup in (self.chapterdict.get('taskgroups') or [])]

    def _init_from_dict(self, context: str, chapter: b.StrAnyDict):
        b.copyattrs(context,
                    chapter, self,
                    mustcopy_attrs='name',
                    mustexist_attrs='taskgroups',
                    cancopy_attrs='title,slug')

    def _init_from_file(self, context: str, course: Course):
        pass  # only present in builder class


class Taskgroup(el.Part):
    TOC_LEVEL = 1  # indent level in table of contents
    course: Course
    chapter: Chapter
    tasks: list['Task']

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        context = f"taskgroup '{name}' in chapter '{self.chapter.name}'"
        self.course.namespace_add(self)
        self._init_from_dict(context, self.taskgroupdict)
        self._init_from_file(context, self.chapter)
        self._create_tasks()

    def _create_tasks(self):
        self.tasks = [Task(taskdict['name'], parent=self, taskgroup=self).from_json(taskdict)
                      for taskdict in self.taskgroupdict['tasks']]

    def _init_from_dict(self, context: str, taskgroupdict: b.StrAnyDict):
        b.copyattrs(context,
                    taskgroupdict, self,
                    mustcopy_attrs='name',
                    cancopy_attrs='tasks, title, slug',
                    mustexist_attrs='taskgroups')

    def _init_from_file(self, context: str, chapter: Chapter):
        pass  # exists only in builder
