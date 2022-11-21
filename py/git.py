"""Technical operations for reading information from git repos."""
import dataclasses
import datetime as dt
import re
import subprocess as sp
import typing as tg

import base as b

LOG_FORMAT_SEPARATOR = '\t'
LOG_FORMAT = "%h%x09%ae%x09%at%x09%GF%x09%s"  # see notes at attributes of Commit or git help log "Pretty Formats"

@dataclasses.dataclass
class Commit:
    hash: str  # %h
    author_email: str  # %ae
    author_date: dt.datetime  # converted from %at
    key_fingerprint: str  # %GF
    subject: str  # %s
    
    
def get_commits() -> tg.Sequence[Commit]:
    result = []
    gitcmd = ["git", "log", f"--format=format:{LOG_FORMAT}"]
    gitrun = sp.run(gitcmd, capture_output=True, encoding='utf8', text=True)
    for line in gitrun.stdout.split('\n'):
        hash, email, tstamp, fngrprnt, subj = tuple(line.split(LOG_FORMAT_SEPARATOR))
        c = Commit(hash, email, 
                   dt.datetime.fromtimestamp(int(tstamp), tz=dt.timezone.utc),
                   fngrprnt, subj)
        result.append(c)
    return result


def get_file_version(refid: str, filename: str, encoding=None) -> tg.AnyStr:
    raw = sp.check_output(f"git show {refid}:{filename}", shell=True)
    if encoding:
        return raw.decode(encoding=encoding)
    else:
        return raw


def get_remote_origin() -> str:
    """The local repo's 'origin' remote"""
    git_remote = sp.check_output("git remote -v show", shell=True).decode('utf8')
    # e.g.:  origin  git@github.com:myaccount/myrepo.git (fetch)
    fetchremote_regexp = r"origin\s+(\S+)\s+\(fetch\)"
    mm = re.search(fetchremote_regexp, git_remote)
    if not mm:
        b.critical(f"cannot find 'origin' URL in  git remote  output:\n{git_remote}")
    return mm.group(1)
