# 2026-04-17 Build natural order into webapp task lists

## Goal

In the webapp's task-list section and work-report table, show the tasks in the order
indicated by the course object's configdict and include headers for each chapter and
for each taskgroup for which a task entry exists.

## Details

In the task-list section, include each chapter 'mychapter' like so:
`<span class"item task-list-chapter">mychapter</span>`

In the task-list section, include a taskgroup 'mytaskgroup' like so:
`<span class"item task-list-taskgroup">mytaskgroup</span>`

In the work.report table, include each chapter 'mychapter' like so:
`<tr class="work-report-chapter-row"><td  class="work-report-chapter-cell">mychapter</td></tr>`

In the work.report table, include a taskgroup 'mytaskgroup' like so:
`<tr class="work-report-taskgroup-row"><td  class="work-report-taskgroup-cell">mytaskgroup</td></tr>`

In both cases, suppress each taskgroup entry that has no task entry below it.
Put in chapter entries even if they have no taskgroup.

## Implementation plan

Do not implement anything yet.
Make a detailed implementation plan and include it below for me to review and modify.
Include arguments why this is not going to break existing functionality, i.e., lose task entries.
Suggest CSS for the new rules.

### Step 1: Add a helper function to produce course-ordered task lists with headers

Add a function (e.g. `ordered_task_entries()`) in `sdrl/webapp/app.py` (or a small helper module)
that, given `course.chapters` and a set of relevant tasknames, returns a flat list of 
`(kind, name)` tuples where `kind` is `'chapter'`, `'taskgroup'`, or `'task'`.

Logic:
```python
def ordered_task_entries(course, tasknames: set[str]) -> list[tuple[str, str]]:
    entries = []
    for chapter in course.chapters:
        chapter_has_content = False
        for taskgroup in chapter.taskgroups:
            tg_tasks = [t.name for t in taskgroup.tasks if t.name in tasknames]
            if not tg_tasks:
                continue  # suppress empty taskgroups
            if not chapter_has_content:
                entries.append(('chapter', chapter.name))
                chapter_has_content = True
            entries.append(('taskgroup', taskgroup.name))
            for tname in tg_tasks:
                entries.append(('task', tname))
        if not chapter_has_content:
            entries.append(('chapter', chapter.name))  # chapter with no taskgroups still shown
    return entries
```

This iterates `course.chapters → chapter.taskgroups → taskgroup.tasks`, preserving their
original order from course.json. Only tasks present in `tasknames` are included, but the
ordering comes from the hierarchy, not from alphabetical sort.

### Step 2: Modify `html_for_layout()` in `app.py` (task-list sidebar)

**Current code** (lines 186–219): Sorts `ctx.tasknames` alphabetically (with instructor 
priority via `checkable_first`), then renders a flat `<li>` list.

**Change**: Replace `sorted(ctx.tasknames, key=checkable_first)` with the ordered list from
`ordered_task_entries(ctx.course, ctx.tasknames)`. Then in the rendering loop, emit:
- For `'chapter'`: a non-clickable `<span class="item task-list-chapter">chaptername</span>` 
  (not wrapped in `<li>`)
- For `'taskgroup'`: a non-clickable `<span class="item task-list-taskgroup">taskgroupname</span>`
  (not wrapped in `<li>`)
- For `'task'`: the existing `<li><a class="item task-link ...">` markup, unchanged.

The instructor `checkable_first` sort is dropped — natural course order replaces it.
(If the instructor sort is desired within each taskgroup, we can add local sorting of
`tg_tasks` in the helper. Please advise.)

### Step 3: Modify `html_for_work_report_section()` in `reports.py` (work report table)

**Current code** (lines 158–166): Uses `sorted_tasks = sorted(ctx.tasknames)` (alphabetical),
iterates to build `<tr>` rows.

**Change**: Replace the iteration with `ordered_task_entries()`. Then:
- For `'chapter'`: emit 
  `<tr class="work-report-chapter-row"><td class="work-report-chapter-cell">name</td></tr>`
- For `'taskgroup'`: emit 
  `<tr class="work-report-taskgroup-row"><td class="work-report-taskgroup-cell">name</td></tr>`
- For `'task'`: emit the existing `<tr>` row, unchanged.

### Step 4: Modify `html_for_work_progress()` in `reports.py`

**Current code** (line 99): Uses `sorted_tasks = sorted(ctx.tasknames)`.

**Change**: Replace with `ordered_task_entries()`, filtering to only `'task'` entries
(chapter/taskgroup entries are irrelevant here since this function just sums values).
No visible output change.

### Step 5: Add CSS rules to `webapp.css`

```css
/* ----- Chapter/taskgroup headers in task-list sidebar: */
.task-list-chapter {
    display: block;
    padding: 0.4rem 0.6rem;
    margin-top: 0.6rem;
    font-weight: bold;
    font-size: 0.95em;
    color: var(--wa-blue-10);
    background-color: var(--wa-blue);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.task-list-taskgroup {
    display: block;
    padding: 0.3rem 0.6rem 0.3rem 1.2rem;
    font-weight: 600;
    font-size: 0.85em;
    color: var(--wa-blue-20);
    background-color: var(--wa-blue-80);
}

/* ----- Chapter/taskgroup headers in work-report table: */
.work-report-chapter-row {
    background-color: var(--wa-blue-20);
}

.work-report-chapter-cell {
    font-weight: bold;
    padding: 0.4rem 0.6rem;
}

.work-report-taskgroup-row {
    background-color: var(--wa-blue-10);
}

.work-report-taskgroup-cell {
    font-weight: 600;
    padding: 0.3rem 0.6rem 0.3rem 1.2rem;
    font-style: italic;
}
```

### Why this will not lose any task entries

1. **Source of truth is unchanged**: `ctx.tasknames` (a `set` derived from student submissions)
   remains the authority on which tasks to show. The helper function only *reorders* these names 
   and adds headers — it never filters tasks out on its own.

2. **Fallback for orphan tasks**: If a task in `ctx.tasknames` is somehow not found in the 
   course hierarchy (e.g., stale submission referencing a removed task), the helper should 
   append it at the end in an "Unknown" section. We can add a check:
   ```python
   seen = {name for kind, name in entries if kind == 'task'}
   for t in sorted(tasknames - seen):
       entries.append(('task', t))
   ```
   This guarantees every taskname in the input appears exactly once in the output.

3. **No mutation**: The course object and ctx.tasknames are only read, never modified.

4. **Even/odd striping**: The work report table's even/odd row classes currently use 
   enumerate index. After the change, the counter must only increment for task rows 
   (chapter/taskgroup header rows don't participate in striping).
