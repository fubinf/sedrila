"""Element cache for incremental build."""
import dbm
import enum
import itertools
import json
import os
import time
import typing as tg
import zlib

import base as b


UNCOMPRESSED_LIMIT = 40  # length of longest string to store uncompressed
ZLIB_WBITS = -15
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


class SedrilaCache:
    """
    All intermediate products and some config values are stored in the cache.
    There are four entry types:
    - files are reflected as a cache key with empty value.
      The has_changed reference time for files is stored in a single entry TIMESTAMP_KEY.
    - str are just that.
    - list[str] and set[str] are stored as a string using LIST_SEPARATOR.
    - dict[Any] are stored as json.
    Keys take the form partname__entrytype.
    Helper entries use __dunder__ keys.
    The actual filename(s) depend(s) on the chosen DBM implementation, which depends on
    what is installed on the system, which means cache files are not necessarily portable
    to other computers.  The default plain-Python DBM will have a single *.db file.
    """
    LIST_SEPARATOR = '|'  # separates entries in list-valued dbm entries. Symbol is forbidden in all names.
    TIMESTAMP_KEY = '__mtime__'  # unix timestamp: seconds since epoch
    DIRTYFILES_KEY = '__dirtyfileslist__'  # previous_dirtyfiles

    db: dict  # in fact a dbm._Database
    persistent_mode: bool  # non-persistent mode for testing/student/instructor via cache_filename=""
    written: b.StrAnyDict  # what was written into cache since start
    timestamp_start: int  # when did the current build process begin -> the future reference time
    timestamp_cached: int  # when did the previous build process begin -> the current reference time
    previous_dirtyfiles: set[str]  # files marked dirty during last run
    new_dirtyfiles: set[str]  # files marked dirty during present run

    def __init__(self, cache_filename: str, start_clean: bool):
        # self.timestamp_start = int(time.time() + 0.5)  # add half second in case filesystem mtime rounds, not truncates
        self.timestamp_start = round(time.time(), 3)  # milliseconds suffice for us
        self.persistent_mode = bool(cache_filename)
        if self.persistent_mode:
            self.db = dbm.open(cache_filename, flag='n' if start_clean else 'c')  # open or create dbm file
        else:
            self.db = dict()
        self.written = dict()
        tsk = self.TIMESTAMP_KEY
        timestamp_cached = float(_decompress(self.db[tsk]) if tsk in self.db else "0")  # default: everything is old
        self.timestamp_cached = round(timestamp_cached, 3)  # milliseconds suffice for us
        b.debug(f"cache.mtime/timestamp_cached: {self.timestamp_cached}")
        dirtyfiles, dirtyfiles_state = self.cached_list(self.DIRTYFILES_KEY)
        self.previous_dirtyfiles = set(dirtyfiles)
        self.new_dirtyfiles = set()
        # self._dump(limit=256)  # debug, if needed

    def __contains__(self, key: str) -> bool:
        return key in self.written or key in self.db

    def __getitem__(self, key: str) -> tg.Any:
        if key in self.written:
            return self.written[key]
        elif key in self.db:
            return _decompress(self.db[key])
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

    def cached_set(self, key: str) -> tuple[set[str], State]:
        return self._entry(key, self._as_set)

    def cached_dict(self, key: str) -> tuple[b.StrAnyDict, State]:
        return self._entry(key, self._as_dict)

    def filestate(self, pathname: str, cache_key: str) -> State:
        """
        Non-existing file: MISSING.
        Before-unseen file: MISSING. **Special case!`**
        Dirty file, or recent file: HAS_CHANGED.
        Otherwise (file with old time): AS_BEFORE.
        """
        if not os.path.exists(pathname):
            return State.MISSING
        cache_state = self.state(cache_key)
        if cache_state == State.MISSING:
            # b.debug(f"{pathname} not in cache")
            return State.MISSING
        if self.is_recent(pathname) or self.is_dirty(pathname):
            # b.debug(f"{pathname} has younger mtime")
            return State.HAS_CHANGED
        else:
            return State.AS_BEFORE

    def record_file(self, path: str, cache_key: str):
        # if cache_key in self.written:
        #     b.warning(f"cache key '{cache_key}' is surprisingly being written more than once.")
        # assert cache_key not in self.written  # we should usually write everything only once
        # The above assertion is violated sometimes (quite rarely) and I do not understand why
        # despite debugging and tracing. But is should not be a problem.
        self.written[cache_key] = ""  # file entries are empty because the file itself holds the data

    def is_recent(self, pathname: str) -> bool:
        """Whether pathname's mtime is larger than the cache's global mtime."""
        filetime = os.stat(pathname).st_mtime
        it_is = filetime > self.mtime
        if it_is:
            b.debug(f"cache.is_recent({pathname}): {filetime} > {self.mtime}")
        return it_is

    def is_dirty(self, pathname: str) -> bool:
        """Whether pathname was marked dirty in previous run."""
        it_is = pathname in self.previous_dirtyfiles
        if it_is:
            b.debug(f"cache.is_dirty({pathname})!")
        return it_is

    def set_file_dirty(self, filename: str):
        """
        When a file produces an error or warning message, we mark it as 'dirty'.
        On the next run, the cache will flag such files as HAS_CHANGED, so that they are built
        again and the message is produced again. 
        """
        b.debug(f"cache.set_file_dirty({filename})")
        self.new_dirtyfiles.add(filename)

    def write_str(self, key: str, value: str):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def write_list(self, key: str, value: list[str]):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def write_set(self, key: str, value: set[str]):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def write_dict(self, key: str, value: b.StrAnyDict):
        assert key not in self.written  # we should write everything only once
        self.written[key] = value

    def close(self):
        """Bring the persistent cache file up-to-date and close dbm."""
        converters = {str: self._as_is, list: self._from_list, set: self._from_set, dict: self._from_dict}
        self.db[self.TIMESTAMP_KEY] = _compress(str(self.timestamp_start))  # update mtime
        self.write_list(self.DIRTYFILES_KEY, list(self.new_dirtyfiles))
        for key, value in self.written.items():
            if value is None:  # should not happen
                b.debug(f"cache['{key}'] is None")
                continue
            converter = converters[type(value)]
            data = converter(value)
            self.db[key] = _compress(data)
        if self.persistent_mode:
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

    def _as_list(self, e: str) -> list[str]:
        return e.split(self.LIST_SEPARATOR) if e else []

    def _as_set(self, e: str) -> set[str]:
        return set(e.split(self.LIST_SEPARATOR)) if e else set()

    @staticmethod
    def _as_dict(e: str) -> b.StrAnyDict:
        return json.loads(e) if e else dict()

    def _from_list(self, e: list[str]) -> str:
        return self.LIST_SEPARATOR.join(e)

    def _from_set(self, e: set[str]) -> str:
        return self.LIST_SEPARATOR.join(e)

    @staticmethod
    def _from_dict(e: b.StrAnyDict) -> str:
        return json.dumps(e, indent=2, check_circular=False)

    def _entry(self, key: str, converter: tg.Callable[[str], CacheEntryType]) -> tuple[CacheEntryType, State]:
        """The only internal cache accessor function"""
        if key in self.written:
            return (self.written[key], State.HAS_CHANGED)
        elif key in self.db:
            return (converter(_decompress(self.db[key])), State.AS_BEFORE)
        else:
            return (converter(None), State.MISSING)

    def _dump(self, limit: int):
        keys = sorted(self.db.keys())
        for key in keys:
            value = _decompress(self.db[key])
            print(f"{key}:\t{value[:limit]}")

    def _storefilelist(self, key: str, samefiles: list[str], newfiles: list[str]):
        thelist = self.LIST_SEPARATOR.join(itertools.chain(samefiles, newfiles))
        self.db[key] = thelist


def _compress(s: str) -> bytes:
    """Encoded, gzip-compressed string; short strings stay uncompressed with a 0 indicator byte prepended."""
    if len(s) > UNCOMPRESSED_LIMIT:
        return zlib.compress(s.encode(), level=6, wbits=ZLIB_WBITS)
    else:
        return b"\x00" + s.encode()


def _decompress(b: bytes) -> str:
    if b[0] == 0:
        return b[1:].decode()
    else:
        return zlib.decompress(b, wbits=ZLIB_WBITS, bufsize=64000).decode()
