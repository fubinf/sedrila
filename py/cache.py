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
import itertools
import os
import time

LIST_SEPARATOR = '|'  # separates entries in list-valued dbm entries. Symbol is forbidden in all names.
USE_CACHE_FLAG_KEY = 'SEDRILA_USE_CACHE'  # name of environment var for activating cache (temporary until completion)
CACHE_FILENAME = '.course.dbm'  # in instructor output directory
LAST_BUILD_TIMESTAMP_KEY = '__last_build_timestamp__'  # Unix timestamp (seconds since epoch)
SEDRILA_VERSION_KEY = '__sedrila_version__'  # base.SEDRILA_VERSION
CHAPTERDIR_FILELIST_KEY = '__chapterdir_files__'  # complete filesnames in chapterdir tree
ALTDIR_FILELIST_KEY = '__altdir_files__'  # complete filesnames in altdir tree
ITREEDIR_FILELIST_KEY = '__itreedir_files__'  # complete filesnames in itreedir tree

class SedrilaCache:
    db: object  # a dbm._Database
    timestamp_start: int
    timestamp_cached: int
    chapterdir_samefiles: list[str]
    chapterdir_newfiles: list[str]

    def __init__(self, cache_filename: str, chapterdir: str, altdir: str, itreedir: str):
        self.timestamp_start = int(time.time())
        self.timestamp_cached = int(self.db.get(LAST_BUILD_TIMESTAMP_KEY, "0"))  # default to "everything is old"
        self.db = dbm.open(cache_filename, flag='c')  # open or create dbm file
        self.chapterdir_samefiles, self.chapterdir_newfiles = (
                self._scandir(chapterdir, self.db.get(CHAPTERDIR_FILELIST_KEY, "")))  # TODO 2: altdir, itreedir


    def __getstate__(self):
        return None  # SedrilaCache has no state that should be pickled

    def __setstate__(self, state):
        pass  # no useful state is restored upon unpickle; one must create a new instance
    
    def finish(self):
        """Finalize the cache: Bring it up-to-date for the next run."""
        self.db[LAST_BUILD_TIMESTAMP_KEY] = str(self.timestamp_start)
        self._storefilelist(CHAPTERDIR_FILELIST_KEY, self.chapterdir_samefiles, self.chapterdir_newfiles)
        # TODO 2: _storefilelist for altdir, itreedir

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
