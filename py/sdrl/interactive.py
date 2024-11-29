import typing as tg
import webbrowser

import blessed

import base as b
import sdrl.constants as c
import sdrl.repo as r


def prefix(entry: r.ReportEntry, selected: dict[str, bool], rejected: dict[str, bool]):
    if selected[entry.taskname]:
        return c.INTERACT_ACCEPT_SYMBOL
    if not(rejected is None) and rejected[entry.taskname]:
        return c.INTERACT_REJECT_SYMBOL
    return " "


def redraw_filter_selection(term: blessed.Terminal, entries: tg.Sequence[r.ReportEntry], rowindex: int, 
                            selected: dict[str, bool], rejected: dict[str, bool], course_url: str):
    print(term.home + term.clear, end="")
    lines = term.height - 1
    print("Move with arrow keys, select/deselect with space/enter, exit with 'Q''")
    if not(course_url is None):
        print("Press 'o' to open task in browser")
        lines = lines - 1
    would_overflow = lines < len(entries)
    rangestart = max(0, rowindex - lines // 2) if would_overflow else 0
    rangeend = min(len(entries), rowindex + lines // 2) if would_overflow else len(entries)
    for i in range(rangestart, rangeend):
        if i == rowindex:
            print(term.reverse, end="")
        else:
            print(term.normal, end="")
        entry = entries[i]
        print(prefix(entry, selected, rejected) + " %4.2fh " % entry.workhoursum + entry.taskpath, end="")
        print(" " * (term.width - 9 - len(entry.taskpath)))  # padding to end of line
    print(term.normal, end="")  # if we end on the selection


def filter_entries(entries: tg.Sequence[r.ReportEntry], selected: dict[str, bool], 
                   rejected: dict[str, bool] | None, course_url: str | None):
    """Interactively select/reject individual entries."""
    term = blessed.Terminal()
    rowindex = 0
    with term.cbreak(), term.hidden_cursor():
        inp = None
        while not inp or not (str(inp) in "Qq" or str(inp.name) == "KEY_ESCAPE"):
            redraw_filter_selection(term, entries, rowindex, selected, rejected, course_url)
            inp = term.inkey()
            if str(inp) == " " or str(inp.name) == "KEY_ENTER":
                if rejected is None:
                    selected[entries[rowindex].taskname] = not(selected[entries[rowindex].taskname])
                elif rejected[entries[rowindex].taskname]:
                    rejected[entries[rowindex].taskname] = False
                elif selected[entries[rowindex].taskname]:
                    selected[entries[rowindex].taskname] = False
                    rejected[entries[rowindex].taskname] = True
                else:
                    selected[entries[rowindex].taskname] = True
            elif str(inp) == "j" or str(inp.name) == "KEY_DOWN":
                if rowindex < len(entries) - 1:
                    rowindex += 1
            elif str(inp) == "k" or str(inp.name) == "KEY_UP":
                if rowindex > 0:
                    rowindex -= 1
            elif not(course_url is None) and (str(inp) == "o" or str(inp) == "O"):
                webbrowser.open(f"{course_url}/{entries[rowindex].taskname}.html")  # TODO 2 on WSL, see 
                # https://github.com/python/cpython/issues/89752


def select_entries(entries: tg.Sequence[r.ReportEntry]) -> tg.Sequence[r.ReportEntry]:
    """Return only those entries the user interactively keeps checked."""
    selected = {entry.taskname: True for entry in entries}
    filter_entries(entries, selected, None, None)
    return [entry for entry in entries if selected[entry]]


def grade_entries(entries: list[r.ReportEntry], course_url: str, override: bool, filter_method=filter_entries
                  ) -> list[str] | None:
    """
    Mark entries in list as accepted if they are and count rejection if not.
    Returns list of new rejections because the count is not enough to know whether they were rejected in current run
    """
    submission = b.slurp_yaml(c.SUBMISSION_FILE)
    selected = {entry.taskname: currently_accepted(submission, entry, override) for entry in entries}
    rejected = {entry.taskname: currently_rejected(submission, entry, override) for entry in entries}
    filter_method(entries, selected, rejected, course_url)
    if not any(selected.values()) and not any(rejected.values()):
        return None  # nothing to do

    def processed(entry: r.ReportEntry) -> r.ReportEntry | None:
        rejections, accepted = entry.rejections, entry.accepted
        if selected[entry.taskname]:
            if override and currently_accepted(submission, entry, override):
                selected[entry.taskname] = False
                return None
            accepted = True
        if rejected[entry.taskname]:
            if override and currently_rejected(submission, entry, override):
                rejected[entry.taskname] = False
                return None
            rejections += 1
        return r.ReportEntry(entry.taskname, entry.taskpath, entry.workhoursum, entry.timevalue, 
                             rejections, accepted)

    for i in reversed(range(len(entries))):
        entries[i] = processed(entries[i])
        if not entries[i]:
            del entries[i]
    return [key for key, value in rejected.items() if value]


def currently_accepted(submission: b.StrAnyDict, entry: r.ReportEntry, override: bool) -> bool:
    return entry.accepted if override else r.is_accepted(submission.get(entry.taskname) or "")


def currently_rejected(submission: b.StrAnyDict, entry: r.ReportEntry, override: bool) -> bool:
    return not(currently_accepted(submission, entry, override)) if override \
        else r.is_rejected(submission.get(entry.taskname) or "")
