"""
Build cache to be used by author mode.
So far incomplete and not active by default.
Can be activated by setting the SEDRILA_USE_CACHE environment variable to any value.
There is currently a simplistic cache mode (using b.CACHE_FILE) controlled by the --cache option.
The present mechanism will eventually replace it. Both cannot be used at the same time.

How it works:
- When initialized, will scan dir trees for unchanged files (_samefiles) and
  new or modified files (_newfiles) relative to last_build_timestamp
- When closed, will store the union of these lists and new last_build_timestamp
- Records and returns dependency lists
- Records and returns tocs and contents
- Answers rendering need questions
"""

import dbm
import enum
import itertools
import os
import time
import typing as tg

import base as b

# states of Elements wrt a Product or wrt the cache
class State(enum.StrEnum):
    """
    nonexisting is a non-file/non-cacheentry: must build.
    has_changed is a younger file or freshly written cache entry: must build or have built.
    as_before is an old file or not-overwritten cache entry: need not build or have not built.
    """
    UNDETERMINED = 'undetermined'  # before do_evalute_state
    NONEXISTING = 'nonexisting'  # for Source or before build: must build; impossible after build
    HAS_CHANGED = 'has_changed'  # for Source or before build: must build; after build: have built
    AS_BEFORE = 'as_before'  # for Source or before build: need not build; after build: have not built

LIST_SEPARATOR = '|'  # separates entries in list-valued dbm entries. Symbol is forbidden in all names.
TIMESTAMP_KEY = '__mtime__'  # unix timestamp: seconds since epoch

class SedrilaCache:
    """
    All intermediate products and some config values are stored in the cache,
    files (source or target) are reflected as a cache key with empty value.
    The has_changed reference time for files is stored in a single entry TIMESTAMP_KEY.
    """
    db: dict  # in fact a dbm._Database
    written: b.StrAnyDict  # what was written into cache since start
    timestamp_start: int  # when did the current build process begin -> the future reference time
    timestamp_cached: int  # when did the previous build process begin -> the current reference time
    chapterdir_samefiles: list[str]
    chapterdir_newfiles: list[str]

    def __init__(self, cache_filename: str, chapterdir: str, altdir: str, itreedir: str):
        self.timestamp_start = int(time.time())
        self.timestamp_cached = int(self.db.get(TIMESTAMP_KEY, "0"))  # default to "everything is old"
        self.db = dbm.open(cache_filename, flag='c')  # open or create dbm file
        self.written = dict()

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

    def filestate(self, pathname: str) -> State:
        """
        Non-existing file: nonexisting.
        Before-unseen file or file with new time: has_changed (and now the file has been seen).
        File with old time: as_before.
        New time means the existing file has mtime later than start of previous build.
        """
        if not os.path.exists(pathname):
            return State.NONEXISTING
        cache_state = self.state(pathname)
        if cache_state == State.NONEXISTING:
            return State.HAS_CHANGED
        filetime = os.stat(pathname).st_mtime
        if filetime > self.mtime:
            return State.HAS_CHANGED
        else:
            return State.AS_BEFORE

        """Finalize the cache: Bring it up-to-date for the next run."""
        self.db[TIMESTAMP_KEY] = str(self.timestamp_start)  # update mtime
        for key, value in self.written.items():
            self.db[key] = value

    def item(self, key: str) -> tuple[tg.Any, State]:
        if key in self.written:
            return (self.written[key], State.HAS_CHANGED)
        elif key in self.db:
            return (self.db[key], State.AS_BEFORE)
        else:
            return (None, State.NONEXISTING)

    def state(self, key: str) -> State:
        if key in self.written:
            return State.HAS_CHANGED
        elif key in self.db:
            return State.AS_BEFORE
        else:
            return State.NONEXISTING

    def _scandir(self, dirname: str, cached_filelist: str) -> tuple[list[str], list[str]]:
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
