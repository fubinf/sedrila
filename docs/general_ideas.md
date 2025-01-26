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
  This means that much of the information regarding how a course is constructed is accessible to the students.
  The only exception are parts that are considered confidential, such as the text describing how to 
  judge the individual tasks (including exemplary solutions). 
  These can be held in a non-public, second git repo that is made available only to teachers on a one-by-one basis. 
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

- `sedrila author` generates a SeDriLa instance from a SeDriLa template.  
  - The template is a directory tree 
    (maintained in a git repository and developed much like software by the course owners)
    with a prescribed structure that contains all the task descriptions, written in Markdown.
  - The instance is a directory of static HTML pages.
  - The generation is controlled by a configuration file.
- `sedrila student` tells the students how many hours are on their timevalue account so far
  and helps them prepare a submission to an instructor.
- `sedrila instructor` supports instructors when evaluating student solutions:
  retrieving student repos, validating their submission file, 
  recording the instructor's feedback.


## 4. Four views of a course as a directory tree

There are four different versions how the data of a course can be organized.
All four versions share (albeit in different technical forms) the fixed three-level
hierarchy of SeDriLa content: Chapters contain Taskgroups which contain Tasks.

- `author` template: The source files from which a course instance will be generated.  
  Contains three subtrees with corresponding chapter/taskgroup/task content:
  `chapterdir` is the public source tree,
  `altdir` is a confidential source tree containing include files to be used by files in `chapterdir`,
  `itreedir` is a second confidential material tree that will be turned into a ZIP file that
  instructors can download so they can work with e.g. program source code in their IDE.  
  The key file in the template is the main config file, typically named `sedrila.yaml`
- course instance: The websites viewed by the students and the instructors, respectively.  
  The student website is a single flat directory where all required files lie side-by-side.
  The chapter/taskgroup/task nesting is reflected only in the menu rendered into each individual file,
  but not in a nesting of directories.  
  The key file in the student website is `course.json`, which contains all metadata describing the course
  and its instructors that are needed by the `student` and `instructor` commands.  
  The instructor website per default lives in a subdirectory `instructor/` of the student website.
  Its structure corresponds to the student website.  
  The key file is `.htaccess`, which, if the entire tree is deployed on an Apache webserver,
  ensures that only instructors can access the instructor website (by logging in). 
- `student` working directory: The files prepared by the students while working on tasks of the course.  
  Arranged into chapter/taskgroup/task directories.  
  There are two key files here: `student.yaml` describes the student and points to a course instance.
  It may also point to another student who is the official work partner.
  `submission.yaml` lists tasks the student submit to instructors and the acceptance/rejection
  decisions of those instructors for those tasks.
- `instructor` course directory:
  A directory containing a number of clones of student working directories.
  Each of them is named by the student's `student_gituser` git username.  
  Key file is `participants.csv`, which lists the students who have been admitted to the course,
  so that `sedrila` can warn when unadmitted students submit solutions.
