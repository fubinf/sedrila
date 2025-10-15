# `sedrila` test framework for SeDriLa courses

**This is work-in-progress. Inofficial. Changing heavily. Partly broken. Do not rely on anything here yet.**

A SeDriLa course may deteriorate over time. Or be broken by a change to a task.
A new task can be broken right from the start.

`sedrila author` already provides support for detecting defects in the _formal structure_
of the course: Illegal metadata, broken task/file/glossary references, etc.
But what about the actual task _content_?

`sedrila` should support detecting defects there as well: 
It would be nice to have a framework for automated testing
of a SeDriLa course that can detect at least _some_ types of problem.

The purpose of the present document is currently to support the design process for developing
such automated testing.
(Later on, it may be converted into some kind of user documentation or be removed.)


## 1. Link checking

One aspect of SeDriLa content checking is making sure that any hyperlinks to external resources
work as expected.

Such checking should be integrated into `sedrila author`, to be activated by a new 
option `--check-links`:

- Link checking needs to follow redirects.
- Not all links that work alright also result in HTTP 200 status.
  `sedrila` should probably allow specifying a different (specifically expected for this particular link)
  status code.
- Not all links that work from a technical point of view will also still contain the
  content the task designer expected it to contain.
  `sedrila` should probably allow specifying a key text snipped that must be present in the response?
  Or even require it?

### Implementation for now

External link validation is integrated into `sedrila author` using efficient HEAD requests with comprehensive reporting.

### Features:
- `--check-links [file]`: Validates external links with detailed reporting
- Uses HEAD requests by default, GET only when content validation is needed
- Generates fixed-name reports for easy integration
- Avoids duplicate URL checking for efficiency
- Supports custom validation rules via HTML comments
- Includes comprehensive statistics in reports

### Usage Examples

```bash
# Full link validation with detailed reports  
sedrila author --check-links -- /tmp/output

# Test single file (development/debugging)
sedrila author --check-links /path/to/file.md /tmp/output

# Include beta-stage tasks in link checking (recommended for pre-release validation)
sedrila author --include_stage beta --check-links -- /tmp/output
```

### Custom Validation Rules

You can specify custom validation rules for specific links using HTML comments:

```markdown
<!-- LINK_CHECK: status=404 -->
[Expected 404](https://example.com/notfound)

<!-- LINK_CHECK: content="Expected Text" -->
[Content Validation](https://example.com/page)

<!-- LINK_CHECK: status=302, timeout=30, ignore_ssl=true -->
[Complex validation](https://redirect.example.com)
```

Supported parameters:
- `status=CODE`: Expect specific HTTP status code
- `content="TEXT"`: Require specific text in response body (triggers GET request)
- `timeout=SECONDS`: Custom timeout for this link
- `ignore_ssl=true`: Skip SSL certificate validation

The validation rule applies to the next link found and is then reset.

### Anti-Crawling Protection

Some domains implement aggressive anti-crawling mechanisms that block automated tools while remaining accessible in browsers. The link checker handles this gracefully:

- **Trusted domains**: `linux.die.net`, `baeldung.com`, `labex.io`, `cyberciti.biz`, `code.visualstudio.com`
- **Behavior**: Returns actual HTTP status (403/500) but marks link as valid
- **Reporting**: Clear explanation that these links are accessible despite status codes
- **Console output**: Dedicated "ANTI-CRAWLING WHITELIST NOTE" section

### Output

Reports are generated with fixed names for easy integration:
- JSON report: `link_check_report.json`
- Markdown report: `link_check_report.md`
- Console summary with integrated statistics
- **Anti-crawling sections**: Dedicated reporting for whitelisted domains with explanations

**Note**: Both single-file and full-course testing use the same fixed report names to prevent file accumulation.


## 2. Program testing

Due to `sedrila`'s reliance on `git`, most SeDriLa courses will likely be programming-related
in one way or another. If so, most tasks will involve something that can be executed
and in most cases the task will then specify (precisely or loosely) an expected behavior of that thing.


### 2.1 Command protocols

The first SeDriLa course, `propra-inf`, makes heavy use of command logs ("Kommandoprotokoll"):

- Students submit a `mytaskname.prot` text file that results from running several commands in a command line shell.
- Task authors provide an example `mytaskname.prot` that instructors use for comparison.

`sedrila instructor` should support instructors in this comparison work:

- Require exact commands
- Allow for modest variation in commands (regexp?)
- Allow for large differences in commands? (multiple command variants?)
- Skip checking for unpredictable commands, but alert instructors if/what they need to check manually.
- Allow for modest variation in outputs (regexp?)
- Allow for large differences in outputs??
- Skip checking for unpredictable outputs, but alert instructors if/what they need to check manually.

`sedrila` needs to provide syntactical mechanisms for specifying the checks 
(with validation performed by `sedrila author`)
and execution logic for performing them and reporting when running `sedrila instructor`.

#### Implementation for now

Command protocol checking is now integrated into `sedrila` with two main components Validation and 
Comparison:

##### Annotation Syntax (for authors)

Authors can add validation rules to their example protocol files using `@PROT_CHECK` annotations:

```bash
# @PROT_CHECK: command=exact, output=flexible
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

# @PROT_CHECK: command=regex, regex=echo.*test, output=skip
$ echo "test message"
test message

# @PROT_CHECK: command=multi_variant, variants="pwd|ls", output=exact
$ pwd
/home/user
```

**Supported Command Types:**
- `exact`: Require exact command match (default)
- `regex`: Match command using regex pattern (requires `regex` parameter)
- `multi_variant`: Allow multiple command variants (requires `variants` parameter)
- `skip`: Skip command checking, mark for manual review

**Supported Output Types:**
- `exact`: Require exact output match (default)
- `flexible`: Ignore whitespace differences and empty lines
- `regex`: Match output using regex pattern (requires `regex` parameter)
- `skip`: Skip output checking, mark for manual review

**Additional Parameters:**
- `regex="pattern"`: Regex pattern for command or output matching
- `variants="cmd1|cmd2|cmd3"`: Pipe-separated list of acceptable command variants
- `manual_note="message"`: Note for manual checking instructions

##### Usage Examples

Validate protocol annotations in author files:
```bash
# Validate all protocol files in course (searches both task directories and altdir)
sedrila author --validate-protocols -- /tmp/output

# Validate specific protocol file
sedrila author --validate-protocols /path/to/file.prot /tmp/output

# Note: Unlike --check-links, protocol validation automatically checks ALL files
# regardless of task stage (no need for --include_stage flag)
```

Compare student and author protocol files:
```bash
# Compare student submission with author example
sedrila instructor --check-protocols student.prot author.prot
```

##### Features

- Validation: `sedrila author --validate-protocols` validates annotation syntax
- Comparison: `sedrila instructor --check-protocols` compares student vs author files
- Flexible Matching: Supports exact, regex, flexible, and multi-variant matching
- Manual Review: Flags entries requiring instructor attention
- Comprehensive Reports: JSON and Markdown reports with detailed results
- Error Handling: Graceful handling of malformed files and missing annotations

##### Implementation Details

- Core module: `py/sdrl/protocolchecker.py`
- Tests: `py/sdrl/tests/protocolchecker_test.py` (pytest format)
- Demo: `example_protocol_demo.py`

Run tests:
```bash
cd py
python -m pytest sdrl/tests/protocolchecker_test.py -v
```


### 2.2 Programs

In many cases, the command log will show executions of some program that has fully or
partly been built by the student during that task.
Then the SeDriLa course will usually contain an exemplary version of that (or such a) program.

Ensuring consistency of the SeDriLa means

- Making sure the exemplary program can still be run.
  This is difficult because there may be required preparatory steps in this task
  or preceeding tasks (`requires`), such as installing a runtime system or some library
  (or potentially many other types).
- Making sure the program still produces the (or an) expected command log.
  This is also difficult, for similar reasons than above.


### 2.3 Program snippets

Tasks will often show snippets from programs for various purposes:

- For students to include them into their programs, so they need not write it all themselves.
- For students to view them for learning something.
  Such a snippet may not appear in the solution at all.
- For students to learn how _not_ to do something (anti-patterns).
- For students to use them as a starting point for what they have to write (incomplete snippet).
- And probably some other kinds.

Testing snippets is probably too variable and too hard to be included in `sedrila`
but it would be nice to at least ensure a snippet that is to be included in the student's
solution is identical to the respective part of the exemplary solution.

One approach could be to avoid all redudancy right from the start:
mark the snippet in the exemplary solution and extract it directly from there
when rendering the task in `sedrila author`.
Then testing the snippet would be reduced to testing the program in which it appears.

#### Implementation for now

Snippet extraction and validation is now integrated into `sedrila` with the following components:

##### Annotation Syntax (for authors)

Authors can mark code snippets in solution files using HTML comment markers:

```markdown
<!-- @SNIPPET_START: snippet_id lang=python -->
def example_function():
    return "Hello, World!"
<!-- @SNIPPET_END: snippet_id -->
```

And reference them in task files using:

```markdown
@INCLUDE_SNIPPET: snippet_id from altdir/ch/TaskGroup/solution.md
```

**Snippet Marker Format:**
- Start marker: `<!-- @SNIPPET_START: snippet_id -->` or `<!-- @SNIPPET_START: snippet_id lang=language -->`
- End marker: `<!-- @SNIPPET_END: snippet_id -->`
- The `snippet_id` must match between start and end markers
- Optional `lang=` parameter specifies the programming language for syntax highlighting

**Snippet Reference Format:**
- `@INCLUDE_SNIPPET: snippet_id from filepath`
- The filepath can be relative to the task file or absolute (from project root)
- Paths starting with `altdir/` are resolved from the project root

##### Usage Examples

Validate snippet references in a single file:
```bash
# Validate specific task file
sedrila author --validate-snippets ch/Web/Django/django-project.md /tmp/output
```

Validate all snippet references in the course:
```bash
# Validate all course files (respects --include_stage)
sedrila author --include_stage draft --validate-snippets -- /tmp/output
```

##### Features

- **Snippet Extraction**: Extracts marked code snippets from solution files
- **Reference Validation**: Verifies all `@INCLUDE_SNIPPET` references point to valid snippets
- **Automatic Expansion**: During build, snippet references are replaced with actual code content
- **Path Resolution**: Supports both relative and absolute paths, including `altdir/` references
- **Error Reporting**: Generates JSON and Markdown reports with detailed validation results
- **Marker Validation**: Detects unclosed snippets and mismatched markers

##### Implementation Details

- Core module: `py/sdrl/snippetchecker.py`
- Tests: `py/sdrl/tests/snippetchecker_test.py` (pytest format)
- Integration: Snippet expansion occurs during markdown preprocessing in `py/sdrl/markdown.py`

Run tests:
```bash
cd py
pytest sdrl/tests/snippetchecker_test.py -v
```

##### Benefits

- **Eliminates Redundancy**: Single source of truth for code examples
- **Maintains Consistency**: Changes to solution code automatically update task descriptions
- **Prevents Errors**: Validation ensures all snippet references remain valid
- **Improves Maintainability**: Easier to update code examples across multiple tasks


### 2.4 Other

The above ideas are not readily applicable to all kinds of tasks, for instance

- when a program's (or command's) effect is not expressed as text output;
- when students are given artistic freedom in what to build;
- and probably a number of other cases.

If we stumble over ideas how to cover some of these that are easy to implement,
we may do it.
But more likely we should apply YAGNI here ("you ain't gonna need it")
and not solve problems of which we have not seen any instance.


## 3. Birds-eye view: Recurring issues

So our goal is to find good solutions for the following problems
(in various contexts and forms):

- How to specify the expectation?
- How to realize the technical preconditions for running whatever there is to be run?
- How to cope with unexpected behaviors?
- How to report behaviors and test outcomes in an easy-to-digest manner?
- How and where to wire all this into `sedrila`?