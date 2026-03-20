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

### Findings: Current code vs. lifecycle description

**LC1 — `sedrila student` startup (`subcmd/student.py:cmd_prepare`)**

Mostly matches. One dead-branch bug: `filter_submission()` (`participant.py:413`) checks
`task.remaining_attempts < 0`, but the property is `max(0, ...)` so this can never be true.
Result: "rejected-for-good" tasks (`remaining_attempts == 0`) are not removed by `filter_submission()`.
They are only correctly removed in `cmd_prepare()`. Fix: `< 0` → `<= 0`.

The functional outcome of cmd_prepare matches LC1 (all submittable tasks end up with CHECK or NOCHECK,
non-submittable tasks are removed). The code deletes-then-re-adds NOCHECK entries rather than
preserving them, which is behaviourally equivalent but the comment should reflect reality.

**LC2 — `sedrila student` webapp**

Matches. No fixes needed; add docstring reference.

**LC3 — `sedrila instructor` startup (`subcmd/instructor.py:prepare_workdir`)**

Mostly matches. The FRESH-state filter keeps only CHECK entries (correct). The same `< 0` bug
means a student-crafted CHECK entry for a task with `remaining_attempts == 0` would survive
`prepare_workdir()`'s filter and `filter_submission()` and appear in the instructor webapp.
Fixing the bug closes this gap.

The `possible_submission_states` for instructor in CHECKING state is currently `[CHECK, ACCEPT, REJECT]`.
After adding REJECTOID storage (see LC4) it must include REJECTOID too.

**LC4 — `sedrila instructor` webapp**

REJECTOID is not currently written to `submission.yaml` — only REJECT is ever stored; REJECTOID
is a computed display state from commit history. Per the lifecycle description REJECTOID should be
written to `submission.yaml` when remaining_attempts > 0 after the action.

Impact:
- `participant.py:set_state()`: when instructor sets REJECT, compute remaining_attempts after
  this rejection (current `remaining_attempts - 1`). If > 0 → write REJECTOID; else write REJECT.
- `repo.py:_accumulate_timevalues_and_attempts()`: treat REJECTOID the same as REJECT (increment rejections).
- `participant.py:Student.__init__()`: add REJECTOID to instructor `possible_submission_states`.
- `filter_submission()`: must not reject REJECTOID entries in instructor CHECKING mode (covered by above).

### Changes to make

**Step 1 — Bug fix: `filter_submission()` (`py/sdrl/participant.py:413`)**

```python
# before:
elif task.remaining_attempts < 0:
# after:
elif task.remaining_attempts <= 0:
```

Update warning text: `"has no remaining_attempts (rejected for good)"`.

**Step 2 — Write REJECTOID to submission.yaml on REJECT action**

`py/sdrl/participant.py` — `possible_submission_states` for instructor (`__init__`, lines 173–174):
add `c.SUBMISSION_REJECTOID_MARK` to the list.

`py/sdrl/participant.py` — `set_state()` (lines 449–455): when instructor sets REJECT,
compute `remaining_attempts - 1`; if > 0 use REJECTOID instead of REJECT.

`py/sdrl/repo.py` — `_accumulate_timevalues_and_attempts()` (lines ~249–262):
extend the `elif tasknote.startswith(c.SUBMISSION_REJECT_MARK)` branch to also match REJECTOID.

**Step 3 — Docstrings/comments referencing LC1–LC4**

- `py/sdrl/subcmd/student.py:cmd_prepare()` → LC1
- `py/sdrl/subcmd/student.py:cmd_webapp()` → LC2
- `py/sdrl/participant.py:filter_submission()` → note role in LC1/LC3 paths
- `py/sdrl/subcmd/instructor.py:prepare_workdir()` → LC3
- `py/sdrl/participant.py:set_state()` → LC4, note REJECT vs REJECTOID logic
- `py/sdrl/participant.py:Student.__init__()` → note `possible_submission_states` and LC context

A single sentence "# LC1: …" or docstring reference is sufficient.

**Step 4 — Update `docs/internal_notes.md`**

- Add a section with the Target task solution state life cycle (LC1–LC5) from this PLAN.md.
  This is the authoritative description that code comments will reference.
- Integrate existing section 3 (SUBMISSION_STATE_* process states) as implementation detail of LC3.
- Clarify that REJECTOID is stored in `submission.yaml` (not just a display concept).
- Trim redundant material.

**Step 5 — Update tests**

- `py/sdrl/tests/participant_test.py`: verify `filter_submission()` removes entries for tasks
  with `remaining_attempts == 0`.
- `py/sdrl/tests/repo_test.py`: verify REJECTOID is written to submission.yaml when
  remaining_attempts > 0 after REJECT, and REJECT when remaining_attempts == 0;
  verify `_accumulate_timevalues_and_attempts()` treats REJECTOID as a rejection.

Run: `python -m pytest py/` from repo root.


## What not to do

Do not modify any other files just yet.
Exception: If you need to experiment by changing some tests, do that but restore the originals
when the plan is complete unless a modified test is a test of future functionality in the TDD sense.
