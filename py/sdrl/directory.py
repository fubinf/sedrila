"""Combined Elements registry/factory and build orchestrator."""
import base as b
import typing as tg


class Directory:
    """
    Each Element is registered here and can be accessed by type and name. 
    The Builder knows when to build each and builds them in an order such that 
    when a Product gets built, the state of all its dependencies is already known.
    This order is also fully determined by the Element types alone.
    """
    def __init__(self):
        import sdrl.elements as el
        import sdrl.course as course
        import sdrl.glossary as glossary
        self.managed_types = [
            # Each has a downcased dict attribute use by get_the()/make_the().
            # The ordering is the build ordering:
            el.Sourcefile, el.CopiedFile,
            el.Zipdir, el.Zipfile,
            el.Topmatter, el.Content, course.DerivedMetadata,
            el.IncludeList_s, el.IncludeList_i, el.PartrefList,
            el.Body_s, el.Body_i,
            el.AssumedByList, el.RequiredByList,
            el.Tocline, el.Toc,
            course.Course, course.Chapter, course.Taskgroup, course.Task, glossary.Glossary,
        ]
        for thistype in self.managed_types:
            dictname = thistype.__name__.lower()
            self.__setattr__(dictname, dict())

    def get_the(self, mytype: type, name: str) -> 'sdrl.elements.Element':
        """Retrieve existing object from the directory."""
        the_dict = self._getdict(mytype)
        return the_dict.get(name)

    def make_the(self, mytype: type, name: str, *args, **kwargs) -> 'sdrl.elements.Element':
        """Instantiate object and store it in the directory. Must be a new entry."""
        the_dict = self._getdict(mytype)
        assert name not in the_dict  # if we re-make the same object, the logic is broken
        instance = mytype(name, *args, directory=self, **kwargs)
        the_dict[name] = instance
        return instance

    def take_the(self, mytype: type, name: str, instance):
        """Store the existing element in the directory. Must be a new entry."""
        the_dict = self._getdict(mytype)
        assert name not in the_dict  # if we enter the same object twice, the logic is broken
        the_dict[name] = instance

    def make_or_get_the(self, mytype: type, name: str, *args, **kwargs) -> 'sdrl.elements.Element':
        instance = self.get_the(mytype, name)
        return instance if instance else self.make_the(mytype, name, *args, **kwargs)

    def record_the(self, mytype: type, name, instance):
        """Store existing object into the directory."""
        the_dict = self._getdict(mytype)
        assert name not in the_dict or the_dict[name] is instance  # if we change an entry, the logic is broken
        the_dict[name] = instance

    def build(self):
        alldicts = ((mytype, self._getdict(mytype)) for mytype in self.managed_types)
        for thistype, thisdict in alldicts:
            b.debug(f"building all Elements of type {thistype.__name__}")
            for elem in thisdict.values():
                elem.build()

    def get_all(self, thetype: type) -> tg.Iterator:
        return self._getdict(thetype).values()

    def _getdict(self, thetype: type):
        dictname = thetype.__name__.lower()
        return getattr(self, dictname)
