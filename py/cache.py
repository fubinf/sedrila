"""Element cache for incremental build."""
import dbm
import enum
import itertools
import json
import os
import time
import typing as tg

import base as b


Cacheable = str | list[str] | b.StrAnyDict  # what can be put in the cache
CacheEntryType = None | Cacheable  # what cache queries can return


class State(enum.StrEnum):
    """
    State of an Element wrt a Product or as a cache entry.
    missing is a non-file/non-cacheentry: must build.
    has_changed is a younger file or freshly written cache entry: must build or have built.
    as_before is an old file or not-overwritten cache entry or outputfile: need not build or have not built.
    """
    MISSING = 'MISSING'  # for Source or before build: must build; impossible after build
    HAS_CHANGED = 'HAS_CHANGED'  # for Source or before build: must build; after build: have built
    AS_BEFORE = 'AS_BEFORE'  # for Source or before build: need not build; after build: have not built


LIST_SEPARATOR = '|'  # separates entries in list-valued dbm entries. Symbol is forbidden in all names.
TIMESTAMP_KEY = '__mtime__'  # unix timestamp: seconds since epoch


class SedrilaCache:
    """
    All intermediate products and some config values are stored in the cache.
    There are four entry types:
    - files (source or target) are reflected as a cache key with empty value.
      The has_changed reference time for files is stored in a single entry TIMESTAMP_KEY.
    - str are just that.
    - list[str] are stored as a string using LIST_SEPARATOR.
    - dict[Any] are stored as json.
    Several helper entries use __dunder__ names.
    """
    db: dict  # in fact a dbm._Database
    written: b.StrAnyDict  # what was written into cache since start
    timestamp_start: int  # when did the current build process begin -> the future reference time
    timestamp_cached: int  # when did the previous build process begin -> the current reference time

    def __init__(self, cache_filename: str):
        self.timestamp_start = int(time.time())
        self.db = dbm.open(cache_filename, flag='c')  # open or create dbm file
        self.timestamp_cached = int(self.db.get(TIMESTAMP_KEY, "0"))  # default to "everything is old"
        self.written = dict()
        # self._dump(limit=256)  # debug, if needed

    def __contains__(self, key: str) -> bool:
        return key in self.written or key in self.db

    def __getitem__(self, key: str) -> tg.Any:
        if key in self.written:
            return self.written[key]
        elif key in self.db:
            return self.db[key]
        raise ValueError(key)

    def __setitem__(self, key: str, value: tg.Any):
        self.written[key] = value

    def __getstate__(self):  # for pickle
        return None  # SedrilaCache has no state that should be pickled

    def __setstate__(self, state):  # for unpickle
        pass  # no useful state is restored upon unpickle; one must create a new instance
    
    @property
    def mtime(self) -> int:
        return self.timestamp_cached

    def cached_str(self, key: str) -> tuple[str, State]:
        return self._entry(key, self._as_is)

    def cached_list(self, key: str) -> tuple[list[str], State]:
        return self._entry(key, self._as_list)

    def cached_dict(self, key: str) -> tuple[b.StrAnyDict, State]:
        return self._entry(key, self._as_dict)

    def filestate(self, pathname: str) -> State:
        """
        Non-existing file: nonexisting.
        Before-unseen file or file with new time: has_changed (and now the file has been seen).
        File with old time: as_before.
        New time means the existing file has mtime later than start of previous build.
        """
        if not os.path.exists(pathname):
            return State.MISSING
        cache_state = self.state(pathname)
        if cache_state == State.MISSING:
            # b.debug(f"{pathname} not in cache")
            return State.HAS_CHANGED
        if self.is_recent(pathname):
            # b.debug(f"{pathname} has younger mtime")
            return State.HAS_CHANGED
        else:
            return State.AS_BEFORE

    def is_recent(self, pathname: str) -> bool:
        """Whether pathname's mtime is larger than the cache's global mtime."""
        filetime = os.stat(pathname).st_mtime
        return filetime > self.mtime

    def write_str(self, key: str, value: str):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def write_list(self, key: str, value: list[str]):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def write_dict(self, key: str, value: b.StrAnyDict):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def record_file(self, path: str):
        assert path not in self.written  # we should write everything only once
        self.written[path] = ""  # file entries are empty because the file itself holds the data
    
    def close(self):
        """Bring the persistent cache file up-to-date and close dbm."""
        converters = {str: self._as_is, list: self._from_list, set: self._from_list, dict: self._from_dict}
        self.db[TIMESTAMP_KEY] = str(self.timestamp_start)  # update mtime
        for key, value in self.written.items():
            if value is None:  # should not happen
                b.debug(f"cache['{key}'] is None")
                continue
            converter = converters[type(value)]
            data = converter(value)
            self.db[key] = data  # implicitly further converts str to bytes
        self.db.__exit__()  # dbm file context manager operation 

    def state(self, key: str) -> State:
        if key in self.written:
            return State.HAS_CHANGED
        elif key in self.db:
            return State.AS_BEFORE
        else:
            return State.MISSING

    @staticmethod
    def _as_is(e: str) -> str:
        return e

    @staticmethod
    def _as_list(e: str) -> list[str]:
        return e.split(LIST_SEPARATOR) if e else []

    @staticmethod
    def _as_dict(e: str) -> b.StrAnyDict:
        return json.loads(e)

    @staticmethod
    def _from_list(e: list[str]) -> str:
        return LIST_SEPARATOR.join(e)

    @staticmethod
    def _from_dict(e: b.StrAnyDict) -> str:
        return json.dumps(e, indent=2, check_circular=False)

    def _entry(self, key: str, converter: tg.Callable[[str], CacheEntryType]) -> tuple[CacheEntryType, State]:
        """The only internal cache accessor function"""
        if key in self.written:
            return (self.written[key], State.HAS_CHANGED)
        elif key in self.db:
            return (converter(self.db[key].decode()), State.AS_BEFORE)
        else:
            return (None, State.MISSING)

    def _dump(self, limit: int):
        keys = sorted(self.db.keys())
        for key in keys:
            value = self.db[key]
            print(f"{key}:\t{value[:limit]}")

    def _scandir(self, dirname: str, cached_filelist: str) -> tuple[list[str], list[str]]:  # TODO 2: remove
        """Lists of all (samefiles, newfiles) below dirname according to cached_filelist and timestamp_cached."""
        reftime = self.timestamp_cached  # younger than this (or equal) means new
        knownfiles_set = set(cached_filelist.split(LIST_SEPARATOR))
        samefiles = []
        newfiles = []
        for root, dirs, files in os.walk(dirname):
            for filename in files:
                pathname = os.path.join(root, filename)
                thistime = os.stat(pathname).st_mtime
                if pathname not in knownfiles_set or thistime >= reftime:  # if new or changed
                    newfiles.append(pathname)
                else:
                    samefiles.append(pathname)
        return samefiles, newfiles
        
    def _storefilelist(self, key: str, samefiles: list[str], newfiles: list[str]):
        thelist = LIST_SEPARATOR.join(itertools.chain(samefiles, newfiles))
        self.db[key] = thelist
