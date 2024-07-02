"""Combined Elements registry/factory and build orchestrator."""


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
            el.Sourcefile, el.Outputfile,
            el.Zipdir, el.Zipfile,
            el.Content, el.Topmatter,
            el.Body_s, el.Body_i, el.IncludeList, el.PartrefList,
            el.AssumedByList, el.RequiredByList,
            el.Tocline, el.Toc,
            course.Course, course.Chapter, course.Taskgroup, course.Task, glossary.Glossary,
        ]
        for thistype in self.managed_types:
            dictname = thistype.__name__.lower()
            self.__setattr__(dictname, dict())

    def get_the(self, mytype: type, name: str) -> 'sdrl.elements.Element':
        the_dict = self._getdict(mytype)
        return the_dict.get(name, None)

    def make_the(self, mytype: type, name: str, *args, **kwargs) -> 'sdrl.elements.Element':
        the_dict = self._getdict(mytype)
        assert name not in the_dict  # if we re-make the same object, the logic is broken
        instance = mytype(name, *args, directory=self, **kwargs)
        the_dict[name] = instance
        return instance

    def make_or_get_the(self, mytype: type, name: str, *args, **kwargs) -> 'sdrl.elements.Element':
        instance = self.get_the(mytype, name)
        return instance if instance else self.make_the(mytype, name, *args, **kwargs)

    def build(self):
        alldicts = (self._getdict(mytype) for mytype in self.managed_types)
        for thisdict in alldicts:
            for elem in thisdict.values():
                elem.build()

    def _getdict(self, thetype: type):
        dictname = thetype.__name__.lower()
        return getattr(self, dictname)
