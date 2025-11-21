# `sedrila` use for people defending a SeDriLa against the ravages of time

**All functionality described herein is in alpha development stage and is subject to change!**

The `sedrila maintainer` subcommand provides lightweight tools for maintaining the technical integrity 
of a SeDriLa course without building the course. 
It operates directly on source files for faster execution.

## 1. Purpose and use cases

Course content degrades over time: External links break, example programs fail as dependencies evolve.
The `sedrila maintainer` subcommand provides automated quality checks for:

- Link checking: Validate HTTP/HTTPS URLs in markdown files
- Program testing: Run example programs and verify their output

Unlike `sedrila author` (full course build generating HTML), maintainer tools perform 
quality checks only, operating directly on source files for speed.
Use in local development, CI pipelines, or scheduled maintenance runs.

## 2. Prerequisites

For checking all files: Requires a valid `sedrila.yaml` configuration file in the current directory 
(or specify via `--config <configfile>`).
The configuration file must define `chapterdir` and other course structure settings.
For checking single files: Only that specific file needs to exist.

Function-specific requirements:

- Link checking: Active internet connection
- Program testing: Runtime environments for tested languages (Python 3.11+, Go 1.23+, etc.) 
  and program files in `altdir/itree.zip` (see section 5.1).
  Currently assumes `altdir/` exists in current directory; 
  Maybe TODO: The checker uses `altdir` setting from configuration to locate test files.


## 3. Basic command structure

```bash
sedrila maintainer [options] targetdir
```

Unlike `sedrila author`, the maintainer does not:

- Build HTML files
- Process templates or macros
- Generate student/instructor websites
- Create cache files

Instead, it performs quality checks using the course structure parsing capability of the build system
to correctly identify which files should be checked according to the course configuration.

Function options:

- `--check-links [markdown_file]`: Check URLs for availability
- `--check-programs [program_file]`: Test programs

Common options:

- `--config <configfile>`: Specify configuration file (default: `sedrila.yaml`)
- `--include-stage <stage>`: Include parts with this and higher stage entries (default: `draft` which includes all stages)
- `--log <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--batch`: Use batch/CI-friendly output

Positional arguments:

- `targetdir`: Base directory for reports (required). Reports are written to `targetdir_i` (targetdir + "_i" suffix), following sedrila's convention of separating instructor content from student content.

## 4. Link Checking: `--check-links`

Option `--check-links [markdown_file]` validates external HTTP/HTTPS links found in markdown files.

Link checking is implemented as a `maintainer` subcommand but leverages 
the `author` build system infrastructure for file identification. 
This design follows the DRY (Don't Repeat Yourself) principle by reusing existing build system logic 
rather than reimplementing course structure parsing and metadata processing.

When checking all files, the command:
1. Creates a `Coursebuilder` instance to parse `sedrila.yaml`
2. Builds only the essential elements needed for file identification:
   - `Sourcefile`: Registers all source files
   - `Topmatter`: Parses YAML metadata from markdown files
   - `MetadataDerivation`: Processes metadata and evaluates stage filtering
3. Extracts the list of markdown files that need checking (respecting configuration and stages)
4. Checks links and generates reports as build products 

Without an argument, it checks all course files using the build system to identify files 
(respects `sedrila.yaml` configuration, only checks configured taskgroups). 
With a file argument, it checks only that specific file.
Uses the `--include-stage` option to control which development stages are checked (default: `draft`, which includes all stages).
Checks both `chapterdir` and `altdir` files (altdir files discovered via path replacement).
Uses HEAD requests by default for efficiency, falling back to GET only when content validation is needed.
Generates a fixed-name markdown report: `link_check_report.md` in `targetdir_i`.
Supports custom link validation rules via HTML comments in markdown files.
Avoids checking duplicate URLs and includes comprehensive statistics in reports.
When checking all files, use `--` to separate options from the positional `targetdir` argument.
Examples:
- `sedrila maintainer --check-links -- /tmp/linkcheck` (check all course files, all stages)
- `sedrila maintainer --include-stage beta --check-links -- /tmp/linkcheck` (check only beta stage)
- `sedrila maintainer --check-links ch/Chapter1/Task1.md /tmp/linkcheck` (check one specific file)

### 4.1 Technical implementation note

The implementation reuses the build system's metadata processing logic (DRY principle):
- Builds only essential elements: `Sourcefile`, `Topmatter`, `MetadataDerivation`
- This automatically handles stage filtering via `evaluate_stage()`
- Ensures `maintainer` and `author` behavior stay synchronized without code duplication

### 4.2 Link validation rules

By default, links are considered successful if they return 2xx or 3xx status codes.
You can specify custom validation rules using HTML comments before links:

```markdown
<!-- LINK_CHECK: status=403 -->
[Restricted Resource](https://example.com/restricted)

<!-- LINK_CHECK: content="Welcome" -->
[Must contain text](https://example.com/)

<!-- LINK_CHECK: status=302, timeout=30, ignore_ssl=true -->
[Complex validation](https://redirect.example.com)
```

Available rule parameters:

- `status=N`: Expect specific HTTP status code (e.g., `status=404` for intentionally broken links)
- `content="text"`: Verify page contains the given text (triggers GET request instead of HEAD)
- `timeout=N`: Use custom timeout in seconds (default: 20)
- `ignore_ssl=true`: Skip SSL certificate validation

The validation rule applies (only) to the next link found.
<<<<<<< HEAD

=======
>>>>>>> ff3b89a (`--check-links`: improve output/CI display, feedback implemented)

## 5. Program Testing: `--check-programs`

Option `--check-programs [program_file]` tests exemplary programs from `altdir/itree.zip` against their corresponding protocol files.
Without an argument, it tests all programs. With a file argument, it tests only that specific file.
  
How it works:

- Scans `altdir/itree.zip` (directory or ZIP file) for program files and finds corresponding `.prot` files in `altdir/ch/`
- Programs with found test pairs are automatically tested if no markup is present
- Use HTML comments in task `.md` files to control test behavior (skip, partial skip, command override)
- Executes ALL testable commands from `.prot` files and verifies output
- Creates `program_test_report.json` and `program_test_report.md` in `targetdir_i`
  
Examples:

- `sedrila maintainer --check-programs -- /tmp/progtest` (test all programs)
- `sedrila maintainer --check-programs altdir/itree.zip/Sprachen/Go/go-channels.go /tmp/progtest` (test single file)

Maybe TODO?

- Stage filtering (`--include-stage`) is not yet implemented for program testing
- The checker now tests all programs found in `altdir/itree.zip`, regardless of the `--include-stage` parameter
- Unlike `--check-links`, which filters files at runtime based on stage and course configuration, `--check-programs` tests all programs found in `altdir/itree.zip`


### 5.1 Prerequisites

#### 5.1.1 Build

**Important**: Program testing requires `altdir/itree.zip` to exist. This can be either:
- A **directory** `altdir/itree.zip/` containing source program files
- A **ZIP file** `altdir/itree.zip` created during course building

To create the ZIP file, build the course first:

```bash
# Complete build (tests all stages)
sedrila author /tmp/build

# Beta stage only (faster, for quick testing)
sedrila author --include_stage beta /tmp/build

# Then run program tests
sedrila maintainer --check-programs -- /tmp/progtest
```

Without building first, the checker will report "Total Programs: 0" if `altdir/itree.zip` does not exist.

In a GitHub Action, **complete build** should be performed before testing to ensure full coverage.


#### 5.1.2 Operating environment

Program testing requires the following environment:

These requirements evolve as new program types are added to the course. The list below reflects the current set of testable programs.

**Required:**

- **Python**: 3.11 or higher
- **Go**: 1.23 or higher (for Go programs)
- **Program files**: `altdir/itree.zip` must exist (either as a directory with source files or as a built ZIP file)

**Python packages (Sedrila dependencies):**
In pyproject.toml: `[tool.poetry.dependencies]` and `[tool.poetry.group.dev.dependencies]`

**Python packages (additional required):**
- FastAPI programs: fastapi, pydantic, uvicorn

For local testing, ensure these packages are available in your environment.


### 5.2 General behavior

#### 5.2.1 Multi-command testing

The program checker parses and tests **ALL testable commands** from each `.prot` file:

- Each command is executed sequentially with output comparison
- Test only passes if ALL commands succeed
- Detailed reporting shows status for each individual command
- Failed tests show which specific command(s) failed with error details


#### 5.2.2 Automatic cleanup

Generated files are cleaned up before and after each test to ensure a clean environment:

- Database files (`.db`, `.sqlite`, `.sqlite3`)
- Log files (`.log`), temporary files (`.tmp`)
- Python cache (`__pycache__`, `.pyc`)

This prevents test failures caused by residual files from previous runs
and ensures consistency between single program and full course testing.


#### 5.2.3 Test output and reporting

The checker provides comprehensive test reports that display the total number of programs found
and test pairs identified. It shows which programs passed, failed, and were skipped, with detailed
categorization for each status.

For multi-command programs, the output lists each command with a numbered index and shows 
individual pass/fail status (✓ [PASS] or ✗ [FAIL]). Error details are included for failed commands,
and tested commands are clearly separated from skipped ones.

The checker calculates a success rate based on all programs, tracks execution time for each 
command and the overall test run, and provides detailed failure reasons along with manual 
testing requirements when applicable.

Both JSON and Markdown reports are generated with categorized sections (Failed Tests, 
Skipped Tests, Passed Tests) for detailed analysis.


#### 5.2.4 CI/Batch mode

For automated testing environments, the `--batch` flag produces concise output suitable 
for CI systems. The exit status is non-zero (1) when tests fail and zero (0) on success.

All failed tests are summarized at the end of the output for quick error identification,
making it easy to spot issues in automated test runs.
JSON and Markdown reports are always generated regardless of output mode.

Scheduled execution runs link checking every Sunday at 03:00 UTC and program testing 
at 03:30 UTC (see `maintainer-linkchecker.yml` and `maintainer-programchecker.yml`).
Both workflows use the `--batch` flag for CI-friendly output.


### 5.3 Program testing markup

By default, programs are tested automatically. 
You can control test behavior using HTML comment markup in task `.md` files.
The markup can be placed anywhere in the file; a common convention is to place it before the `[INSTRUCTOR]` section.


#### 5.3.1 SKIP markup (manual testing): `@PROGRAM_TEST_SKIP`

Use for programs with non-deterministic output, interactive input, environment-specific output, or complex shell operations.

```markdown
<!-- @PROGRAM_TEST_SKIP: reason="Concurrent execution order is non-deterministic" manual_test_required=true -->
```

Parameters:

- `reason="text"`: Explanation why manual testing is required
- `manual_test_required=true`: Marks program for manual testing


#### 5.3.2 PARTIAL markup (manual/automation mix): `@PROGRAM_TEST_PARTIAL`

Use when some commands are testable while others require manual verification.

```markdown
<!-- @PROGRAM_TEST_PARTIAL: skip_commands_with="Traceback,MemoryError" skip_reason="Different stack depths lead to inconsistent output" testable_note="Other commands can be automatically tested" -->
```

Parameters:

- `skip_commands_with="keyword1,keyword2"`: Skip commands containing these keywords in output
- `skip_reason="text"`: Explanation for skipping certain commands
- `testable_note="text"`: Note about which commands are testable


#### 5.3.3 OVERRIDE markup (expected command mismatches): `@PROGRAM_TEST_OVERRIDE`

Use when `.prot` files reference incorrect command names.

```markdown
<!-- @PROGRAM_TEST_OVERRIDE: original_command="go run main.go" correct_command="go run go-channels.go" reason=".prot file uses main.go but actual file is go-channels.go" -->
```

Parameters:

- `original_command="cmd"`: Command as written in `.prot` file
- `correct_command="cmd"`: Correct command to execute
- `reason="text"`: Explanation for the override


#### 5.3.4 General PROGRAM_TEST markup (reserved for future use): `@PROGRAM_TEST`

This is a general-purpose markup reserved for future extensions.
Currently, it supports a `notes` parameter for documentation purposes, but this parameter is not used by the test runner.

```markdown
<!-- @PROGRAM_TEST: notes="Additional information about this program test" -->
```

Parameters:
- `notes="text"`: Documentation notes (currently not used by the test runner)

**Behavior:** Programs with this markup are tested normally, exactly like programs without any markup.
The markup serves only as a placeholder for potential future functionality.


#### 5.3.5 No markup (normal automated testing)

Programs with deterministic output require no special markup and are tested automatically.
This is functionally equivalent to using `@PROGRAM_TEST` with documentation notes.
