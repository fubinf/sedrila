from blessed import Terminal
import typing as tg

import base as b
import sdrl.repo as r

def prefix(entry: r.ReportEntry, selected: dict[str, bool], rejected: dict[str, bool]):
    if selected[entry[0]]:
        return "✓"
    if not(rejected is None) and rejected[entry[0]]:
        return "X"
    return " "


def redraw_filter_selection(term: Terminal, entries: tg.Sequence[r.ReportEntry], rowindex: int, selected: dict[str, bool], rejected: dict[str, bool]):
    print(term.home + term.clear, end="")
    print("Move with arrow keys, select/deselect with space/enter, exit with escape")
    rangestart = max(0, rowindex - term.height / 2)
    rangeend = min(len(entries), rowindex + term.height / 2)
    for i in range(rangestart, rangeend):
        if i == rowindex:
            print(term.reverse, end="")
        else:
            print(term.normal, end="")
        print(prefix(entries[i], selected, rejected) + " %4.2fh " % entries[i][1] + entries[i][0], end="")
        print(" " * (term.width - 9 - len(entries[i][0]))) #padding to end of line
    print(term.normal, end="") #if we end on the selection


def filter_entries(entries: tg.Sequence[r.ReportEntry], selected: dict[str, bool], rejected: dict[str, bool]):
    term = Terminal()
    rowindex = 0
    with term.cbreak(), term.hidden_cursor():
        inp = None
        while not(inp) or not(str(inp) == "q" or str(inp.name) == "KEY_ESCAPE"):
            redraw_filter_selection(term, entries, rowindex, selected, rejected)
            inp = term.inkey()
            if str(inp) == " " or str(inp.name) == "KEY_ENTER":
                if rejected is None:
                    selected[entries[rowindex][0]] = not(selected[entries[rowindex][0]])
                elif rejected[entries[rowindex][0]]:
                    rejected[entries[rowindex][0]] = False
                elif selected[entries[rowindex][0]]:
                    selected[entries[rowindex][0]] = False
                    rejected[entries[rowindex][0]] = True
                else:
                    selected[entries[rowindex][0]] = True
            elif str(inp) == "j" or str(inp.name) == "KEY_DOWN":
                if rowindex < len(entries) - 1:
                    rowindex += 1
            elif str(inp) == "k" or str(inp.name) == "KEY_UP":
                if rowindex > 0:
                    rowindex -= 1


def select_entries(entries: tg.Sequence[r.ReportEntry]):
    selected = {entry[0]: True for entry in entries}
    filter_entries(entries, selected, None)
    return list(filter(lambda entry: selected[entry[0]], entries))


#marks entries as accepted if they are, returns rejections as the count might not be enough to know whether they were rejected in current run
def grade_entries(entries: tg.Sequence[r.ReportEntry]):
    selected = {entry[0]: False for entry in entries}
    rejected = {entry[0]: False for entry in entries}
    filter_entries(entries, selected, rejected)
    if not(any(selected.values())) and not(any(rejected.values())):
        return None
    for i in range(len(entries)):
        entry = list(entries[i])
        if selected[entry[0]]:
            entry[4] = True
        if rejected[entry[0]]:
            entry[3] += 1
        entries[i] = tuple(entry)
    return [key for key, value in rejected.items() if value]
