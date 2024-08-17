"""Combined Elements registry/factory and build orchestrator."""
import itertools

import base as b
import typing as tg


class Directory:
    """
    Each Element is registered here and can be accessed by type and name. 
    The Builder knows when to build each and builds them in an order such that 
    when a Product gets built, the state of all its dependencies is already known.
    This order is also fully determined by the Element types alone.
    """
    def __init__(self, cache):
        import sdrl.elements as el
        import sdrl.course as course
        import sdrl.glossary as glossary
        self.cache = cache
        self.managed_types = [
            # Each has a downcased dict attribute use by get_the()/make_the().
            # The ordering is the build ordering:
            el.Sourcefile, el.CopiedFile,
            el.Zipdir, el.Zipfile,
            el.Topmatter, el.Content, course.MetadataDerivation,
            el.IncludeList_s, el.IncludeList_i, el.TermrefList,
            el.Body_s, el.Body_i, el.Glossarybody,
            el.Toc, el.LinkslistBottom,
            course.Course, course.Chapter, course.Taskgroup, course.Task, glossary.Glossary,
        ]
        for thistype in self.managed_types:
            dictname = thistype.__name__.lower()
            setattr(self, dictname, dict())

    def get_the(self, mytype: type, name: str) -> 'sdrl.elements.Element':
        """Retrieve existing object from the directory."""
        the_dict = self._getdict(mytype)
        return the_dict.get(name)

    def make_the(self, mytype: type, name: str, **kwargs) -> 'sdrl.elements.Element':
        """Instantiate object and store it in the directory. Must be a new entry."""
        the_dict = self._getdict(mytype)
        if name in the_dict:
            b.debug(f"make_the: overwriting internal entry {mytype.__name__}({name}) from {b.caller(1)}")
        instance = mytype(name, directory=self, **kwargs)
        the_dict[name] = instance
        return instance

    def take_the(self, mytype: type, name: str, instance):
        """Store the existing element in the directory. Must be a new entry."""
        the_dict = self._getdict(mytype)
        if name in the_dict:
            b.debug(f"take_the: overwriting internal entry {mytype.__name__}({name})")
        the_dict[name] = instance

    def make_or_get_the(self, mytype: type, name: str, **kwargs) -> 'sdrl.elements.Element':
        instance = self.get_the(mytype, name)
        return instance if instance else self.make_the(mytype, name, **kwargs)

    def record_the(self, mytype: type, name, instance):
        """Store existing object into the directory."""
        the_dict = self._getdict(mytype)
        if name in the_dict and the_dict[name] is not instance:
            b.debug(f"record_the: overwriting internal entry {mytype.__name__}({name})")
        the_dict[name] = instance

    def build(self):
        alldicts = ((mytype, self._getdict(mytype)) for mytype in self.managed_types)
        for thistype, thisdict in alldicts:
            b.debug(f"building all Elements of type {thistype.__name__}")
            for elem in thisdict.values():
                elem.build()

    def get_all(self, what: type | str) -> tg.Iterable:
        """All entries with a given type or with a given name (in any type)."""
        if isinstance(what, type):
            return self._getdict(what).values()
        # collect all elements with name what:
        result = []
        for typ in self.managed_types:
            candidate = self._getdict(typ).get(what, None)
            if candidate:  # skip types with no such entry
                result.append(candidate)
        return result

    def get_all_outputfiles(self) -> tg.Iterator:
        import sdrl.elements as el
        iterators = [self.get_all(t) for t in self.managed_types
                     if issubclass(t, el.Outputfile)]
        return itertools.chain(*iterators)

    def _getdict(self, thetype: type):
        dictname = thetype.__name__.lower()
        return getattr(self, dictname)
