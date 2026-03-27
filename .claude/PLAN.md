2026-03-20: Getting the task acceptance lifecycle right

## Goal

Have `submission.yaml` entries and task states that follow clear concepts, are documented,
provide clear feedback to students, allow overriding submission limits in exceptional cases,
and is immune against manipulation by students.


## Target task solution state life cycle (LC)

The basic idea of sedrila is: a student works on a task, submits it.
Instructor accepts it. Or instructor rejects it and the student will resubmit it later.
The process must be immune against whatever the student writes into `submission.yaml`
and process only the sensible entries.


### LC1: `sedrila student` prepares list of submittable tasks

We call a task **submittable** if a task of that name exists and that task is neither in state `ACCEPT`
nor in state `REJECT` with `remaining_attempts <= 0`.

The student submission command 
- determines each tasks' state from the commit history,
- finds all worktime entries in the commit history,
- reads the existing `submission.yaml`, ignoring all entries pertaining to non-submittable tasks,
  and entries whose mark is neither `CHECK` nor `NOCHECK`,
- adds as `NOCHECK` all further submittable tasks that have a worktime entry,
- persists `submission.yaml`.


### LC2: student selects tasks for submission

sedrila then starts the webapp in which the student can toogle the submittable tasks between
`CHECK` and `NOCHECK`, each time persisting `submission.yaml`.
The student commits the resulting `submission.yaml`.
Note that sedrila cannot keep the student from modifying `submission.yaml` arbitrarily before the commit.


### LC3: `sedrila instructor` cleans up `submission.yaml`

`sedrila instructor` treats `submission.yaml` as untrusted when it is identical to the state
it had in the repos' youngest commit (no matter whether this is a student commit or instructor commit)
and as trusted if it differs.

Upon reading an untrusted `submission.yaml`, sedrila will 
remove all entries for non-submittable tasks,
remove all entries with a mark other than `CHECK`,
then persist `submission.yaml`.


### LC4: instructor checks submission

sedrila now starts the webapp, allowing the instructor to toggle tasks between
`ACCEPT`, `REJECT`/`REJECTOID`, and `CHECK`, each time persisting `submission.yaml`.
A `REJECT` action will result in state `REJECTOID` (meaning this string is shown in `submission.yaml`)
if the task has remaining_attempts after the action
and in state `REJECT` if it has not.


### LC5: instructor commits

When the instructor commits the so-prepared `submission.yaml` (as an instructor-signed commit!),
the acceptances and rejections become part of the validated repo version history
and will show up correspondingly in a timevalue report.

What instructors must not do is stash a `submission.yaml` during review and blindly pull further
student commits, because that could result in misleading entries in `submission.yaml`
that would become trusted upon unstash.


## What to do

- check whether `sedrila student` startup behavior is in line with LC1
  and carefully note any differences,
- check whether `sedrila student` webapp behavior is in line with LC2
  and carefully note any differences,
- check whether `sedrila instructor` startup behavior is in line with LC3
  and carefully note any differences,
- check whether `sedrila instructor` webapp behavior is in line with LC4
  and carefully note any differences,
- always keeping in mind that each process could be interrupted at any time.
- Write a plan for what needs modification (and why) into section "Implementation plan"
- At a minimum, the respective functions' comments (or docstring) should refer to
  LC1 to LC4 explicitly.
- If anything else is changed, adapt the tests accordingly.
- Include plan items for reworking `docs/internal_notes.md` such that 
  a) the Target task solution state life cycle (LC) from above is described there and
  b) existing material there pertaining to this topic is trimmed accordingly 
  (or both are integrated with each other). 


## Implementation plan

2026-03-27: Remove OVERRIDE_PREFIX, fix REJECTOID serialization bug, remove dead code.

### Diagnosis

The test `participant_test.py` fails at line 101: `task2.rejections` is 0 instead of 1.
Root cause: `Submissions.submission_yaml` (participant.py:141-146) chains `to_check`,
`accepted`, and `rejected` but **omits rejectoid entries**, so REJECTOID tasks vanish when
`save_submission()` writes the file. The committed submission.yaml has no REJECTOID entry,
so `_accumulate_timevalues_and_attempts()` has nothing to count.

`_accumulate_timevalues_and_attempts()` itself would handle REJECTOID correctly already
(`"REJECTOID".startswith("REJECT")` is True), but it never sees the entry.

Separately, `SUBMISSION_OVERRIDE_PREFIX` ("OVERRIDE_") is dead code:
- The only function that wrote it (`submission_file_entries()`) has had zero callers since 2025-02-07.
- The read-side logic in `_accumulate_timevalues_and_attempts()` handles it but nothing produces it.
- The LC1-LC5 lifecycle replaces it with a simpler model: the webapp enforces `remaining_attempts`;
  instructors can manually write ACCEPT/REJECT/REJECTOID if they need to override.

### Step 1 — Fix `Submissions.submission_yaml` (the actual bug)
**File:** `py/sdrl/participant.py:125-146`

Add a `rejectoid` property and include it in `submission_yaml`:
```python
@property
def rejectoid(self) -> ...:
    return filter(lambda t: t[1].state == SubmissionTaskState.REJECTOID, self._task_items)
```
Then in `submission_yaml`, change the chain to:
```python
itertools.chain(self.to_check, self.accepted, self.rejected, self.rejectoid)
```

### Step 2 — Remove SUBMISSION_OVERRIDE_PREFIX and dead code
**File:** `py/sdrl/constants.py:26` — delete `SUBMISSION_OVERRIDE_PREFIX = "OVERRIDE_"`.

**File:** `py/sdrl/repo.py`:
- `is_accepted()` (lines 207-211): remove override-stripping, simplify to
  `return tasknote.startswith(c.SUBMISSION_ACCEPT_MARK)`.
- `is_rejected()` (lines 214-218): same simplification.
- `submission_file_entries()` (lines 221-236): delete entirely (dead code, zero callers).
- `_accumulate_timevalues_and_attempts()` (lines 239-264): remove all override logic.
  Simplified:
  ```python
  if tasknote.startswith(c.SUBMISSION_ACCEPT_MARK):
      task.accept_date = check.commit.author_date
  elif tasknote.startswith(c.SUBMISSION_REJECT_MARK):  # catches REJECT and REJECTOID
      if not task.is_accepted:
          task.rejections += 1
  ```

### Step 3 — Verify
Run `python -m pytest py/` — the assertion `(task1.rejections, task2.rejections) == (0, 1)` should pass.
