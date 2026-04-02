2026-04-02 rework MANUAL bookkeeping

## 1. Goal

Standardize manual booking reason types and enforce a closed reason type universe.


## 2. What to do

Introduce an optional key `manual_bookings` for `sedrila.yaml` in the JSON schema.
Give it two mandatory subkeys:
`types` is a list of strings.
`explanation_url` is a URL.

Add these to `sedrila.yaml` in the test data: `types: REASON-A, REASON-B`,
`explanation_url: http://example.org/mypath/manual_booking_types_explanation.html`

In author.py, export both to course.json.

In webapp (for student as well as instructor) check for presence of the `manual_bookings` key
to decide a) whether or not to show the manual bookings summary row and
b) whether to even look for manual booking commits.

On the page that lists the manual bookings, make any entry refering to a reason from `types`
(say, REASON-A) a hyperlink to the fragment of the same name on the `explanation_url` page.

`book_command()` in `instructor.py` checks for presence of the `manual_bookings` key and
terminates with an error message "manual bookings are not avaiable for course {course_url}"
if missing.

`book_command()` gets a new command format: 
`sedrila instructor book --timevalue timevalue reason`.
The reason must be either a task name or one of the `manual_bookings.types`.
If it is not, terminate with error message 
"Reason must be either a task name or one of these types:\n{manual_bookings.types}"

Open the editor in both cases: task as a reason or named type as a reason.
The first line of the initial content is defined completely by the command arguments,
only the remainder comes from the template.

When collecting manual bookings from the list of commits, identify invalid ones by the same rule,
report them as a warning, and then ignore them.
