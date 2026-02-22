"""
CourseSI: Course subclass for student and instructor subcommands.
"""
import base as b
from sdrl.course import Course, Chapter, Taskgroup, Task


class CourseSI(Course):
    """Course for cmds student and instructor. Init from c.METADATA_FILE."""
    MUSTCOPY_ADDITIONAL = ''
    CANCOPY_ADDITIONAL = ''

    chapters: list['Chapter']

    def __init__(self, configdict: b.StrAnyDict, context: str):
        super().__init__(configdict=configdict, context=context)
        self.parttype = dict(Chapter=Chapter, Taskgroup=Taskgroup, Task=Task)
        self._init_parts(self.configdict)

    def _init_parts(self, configdict: dict):
        self.chapters = [Chapter(ch['name'], parent=self, chapterdict=ch)  # noqa
                         for ch in configdict['chapters']]
