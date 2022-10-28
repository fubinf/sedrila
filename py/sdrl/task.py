"""Representation and operations for a single task within a SeDriLa course."""
import logging
import os.path
import typing as tg

import yaml

import base

logger = logging.getLogger()

difficulty_levels = ('verylow', 'low', 'medium', 'high')
enthusiasm_levels = ('none', 'low', 'medium', 'high')

class Task:
    file: str  # the originating pathname
    metadata_text: str  # the entire YAML character stream
    content: str  # the entire first markdown block
    tutorcontent: str  # the entire second markdown block
    taskname: str  # the key by which we access the Task object
    
    title: str  # title: value
    description: str  # description: value (possibly multiple lines)
    effort: tg.Union[int, float]  # effort: (in half hours)
    difficulty: str  # difficulty: value (one of Task.difficulty_levels)
    enthusiasm: str  # enthusiasm: value (one of Task.enthusiasm_levels)
    depends_on: tg.Sequence[str]  # tasknames
    todo: tg.Sequence[tg.Any]  # list of potentially YAML stuff

    chaptername: str  # where the task belongs according to the config
    taskgroupname: str  # where the task belongs according to the config

    def __init__(self, file: str, text: str=None):
        """Reads task from a file or multiline string."""
        self.file = file
        if not text:
            text = base.slurp(file)
        parts = text.split("---\n---\n")
        if len(parts) < 3:
            raise ValueError(f"{self.file} is not a task file: must have three parts separated by double triple-dashes")
        self.metadata_text = parts[0]
        self.content = parts[1]
        self.tutorcontent = parts[2]  # possible further parts are internal notes and are ignored
        self._read_metadata()
    
    def assign(self, chaptername: str, taskgroupname: str):
        """Assign the task to a chapter and taskgroup."""
        self.chaptername = chaptername
        self.taskgroupname = taskgroupname

    def _read_metadata(self):
        """Parse and check (locally only) the metadata."""
        # ----- get taskname from filename:
        nameparts = os.path.basename(self.file).split('.')
        assert len(nameparts) == 2  # taskname, suffix 'md'
        self.taskname = nameparts[0]  # must be globally unique
        try:
            #----- parse YAML data:
            metadata = yaml.safe_load(self.metadata_text)
        except yaml.YAMLError as exc:
            logger.error(f"{self.file}: metadata YAML is malformed: {str(exc)}")
        try:
            #----- get mandatory attributes from YAML:
            self.title = metadata['title']
            self.description = metadata['description']  # for tooltip or proper HTML
            self.effort = metadata['effort']
            self.difficulty = metadata['difficulty']
        except AttributeError as exc:
            logger.error(f"{self.file}: {str(exc)}")
        # ----- get optional attributes from YAML:
        self.enthusiasm = getattr(metadata, 'enthusiasm', 'medium')
        self.depends_on = self._as_list(getattr(metadata, 'depends_on', []))
        self.todo = self._as_list(getattr(metadata, 'todo', []))
        #----- semantic checks:
        ...  # TODO 2
            
    def _as_list(self, obj) -> tg.List:
        return obj if isinstance(obj, list) else list(obj)


Tasks = tg.Mapping[str, Task]  # taskname -> task