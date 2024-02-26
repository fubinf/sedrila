# sedrila General Ideas

## 1. What is a self-driven lab course (here known as "a SeDriLa")?

- There is a large number of small tasks, each worth a certain number of work hours
- Within loose constraints, students can pick which tasks they want to work on
- Each task results in a commit (or several) in that student's git repository
- At certain times, students can submit a batch of finished tasks to an instructor or teaching assistant
- The instructor checks some of the task's solution commits and then
  either accepts or rejects the entire batch.
- If accepted, the timevalue assigned to those tasks is booked onto the student's timevalue account,
  which is also represented by a series of commits in the student's git repository.
- When enough hours have accumulated there, that student has successfully finished the course.

Instructor commits are signed such that they cannot be forged.


## 2. `sedrila` is opinionated

- It assumes that the course content is so useful and motivating for the students
  that they are unlikely to cheat.
- It assumes that SeDriLas are (or could become) Open Educational Resources.
  This means that all information that is accessible to the teaching assistants 
  is also accessible to the students.
- It takes a low-tech approach and assumes that content has a simple structure
  because the tasks rely heavily on _external_ materials available on the web.
  The SeDriLa itself has a simple text layout, few images of its own,
  and no local videos or high-tech active content.  
  The idea behind this is to make it realistic to keep the SeDriLa fresh and up-to-date over time.
- SeDriLas are pass/fail, they are not graded, because that would be incompatible
  with the above goals.


## 3. What does the `sedrila` tool do?

The tool serves three target audiences: 
first course authors, then students, and finally instructors. 
Correspondingly, it basically has three functions:

- `author` generates a SeDriLa instance from a SeDriLa template.  
  - The template is a directory tree 
    (maintained in a git repository and developed much like software by the course owners)
    with a prescribed structure that contains all the task descriptions, written in Markdown.
  - The instance is a directory of static HTML pages.
  - The generation is controlled by a configuration file.
- `student` tells the students how many hours are on their timevalue account so far
  and helps them prepare a submission to an instructor.
- `instructor` supports instructors when evaluating student solutions:
  retrieving student repos, validating their submission file, 
  recording the instructor's feedback.

