"""Technical operations for reading information from git repos."""
import dataclasses
import datetime as dt
import os
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
    

def clone(repo_url: str, targetdir: str):
    os.system(f"git clone {repo_url} {targetdir}")

    
def commits_of_local_repo() -> tg.Sequence[Commit]:
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


def contents_of_file_version(refid: str, filename: str, encoding=None) -> tg.AnyStr:
    raw = sp.check_output(f"git show {refid}:{filename}", shell=True)
    if encoding:
        return raw.decode(encoding=encoding)
    else:
        return raw


def origin_remote_of_local_repo() -> str:
    """The local repo's 'origin' remote, which we assume to exist and to be the relevant remote."""
    git_remote = sp.check_output("git remote -v show", shell=True).decode('utf8')
    # e.g.:  origin  git@github.com:myaccount/myrepo.git (fetch)
    fetchremote_regexp = r"origin\s+(\S+)\s+\(fetch\)"
    mm = re.search(fetchremote_regexp, git_remote)
    if not mm:
        b.critical(f"cannot find 'origin' URL in  git remote  output:\n{git_remote}")
    return mm.group(1)


def pull():
    os.system("git pull")


def username_from_repo_url(repo_url: str) -> str:
    # a repo_url is git@server:useraccount/reponame.git or git@server:useraccount/subset/reponame.git
    repo_url_regexp = r":([\w_\.-]+)/"
    mm = re.search(repo_url_regexp, repo_url)
    if repo_url.startswith("http") or not mm:
        b.critical(f"Git url '{repo_url}' is not usable.\nNeed one like 'git@server:useraccount/reponame.git'.")
    return mm.group(1) if mm else None  # tests will patch b.critical away
