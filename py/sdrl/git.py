"""Reading information from the git repo."""
import dataclasses
import datetime as dt
import subprocess as sp
import typing as tg

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