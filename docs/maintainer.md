# `sedrila maintainer` - Course Maintenance

The `sedrila maintainer` subcommand provides lightweight tools for maintaining course quality
without building the course. It operates directly on source files for faster execution.

## Usage

Basic command structure:

```bash
sedrila maintainer [options]
```

Unlike `sedrila author`, the maintainer does not:
- Build HTML files
- Process templates or macros
- Generate student/instructor websites
- Create cache files

Instead, it performs quality checks directly on source markdown and protocol files.

## Options

Common options:
- `--config <configfile>`: Specify configuration file (default: `sedrila.yaml`)
- `--log <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Link Checking

- Option `--check-links [markdown_file]` validates external HTTP/HTTPS links found in markdown files.
  Without an argument, it checks all course files. With a file argument, it checks only that specific file.
  Uses HEAD requests by default for efficiency, falling back to GET only when content validation is needed.
  Generates fixed-name reports: `link_check_report.json` and `link_check_report.md` in the current directory.
  Supports custom validation rules via HTML comments in markdown files (see examples below).
  Avoids checking duplicate URLs and includes comprehensive statistics in the main report.
  Examples: 
  - `sedrila maintainer --check-links` (check all course files)
  - `sedrila maintainer --check-links ch/Chapter1/Task1.md` (check specific file)

#### Link validation rules

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
- `content="text"`: Verify page contains specific text (triggers GET request instead of HEAD)
- `timeout=N`: Use custom timeout in seconds
- `ignore_ssl=true`: Skip SSL certificate validation

The validation rule applies to the next link found and is then reset.

**Important:** There is no central whitelist for trusted domains. If a link is expected to return
non-2xx/3xx status codes (e.g., 403), you must explicitly declare this with a `LINK_CHECK` comment.
The checker will still make the request to verify the actual status code.

#### CI/CD Integration

Link checking is now used for Github Actions

### Protocol Comparison and Program Testing

- Option `--check-protocols [student_file] [author_file]` compares student protocol files against author
  reference files using `@PROT_CHECK` annotations to validate command execution and output.

- Option `--check-programs` tests exemplary programs from `itree.zip` against their corresponding protocol files.
  Programs are executed and their output is compared with expected results from `.prot` files.
  Uses annotation-based configuration in task `.md` files for flexible test behavior control.
  Generates fixed-name reports: `program_test_report.json` and `program_test_report.md` in the current directory.
  Examples:
  - `sedrila maintainer --check-programs` (test all programs)
  
#### Program testing annotations

By default, programs are tested automatically. You can control test behavior using HTML comment annotations in task `.md` files (typically placed before the `[INSTRUCTOR]` section).

**Available annotation types:**

**1. SKIP annotation** - Programs requiring manual testing:

Use for programs with non-deterministic output, interactive input, environment-specific output, or complex shell operations.

```markdown
<!-- @PROGRAM_TEST_SKIP: reason="Concurrent execution order is non-deterministic" manual_test_required=true -->

[INSTRUCTOR::...]
```

Parameters:
- `reason="text"`: Explanation why manual testing is required
- `manual_test_required=true`: Marks program for manual testing

**2. PARTIAL annotation** - Programs with mixed testability:

Use when some commands are testable while others require manual verification.

```markdown
<!-- @PROGRAM_TEST_PARTIAL: skip_commands_with="Traceback,MemoryError" skip_reason="Different stack depths lead to inconsistent output" testable_note="Other commands can be automatically tested" -->

[INSTRUCTOR::...]
```

Parameters:
- `skip_commands_with="keyword1,keyword2"`: Skip commands containing these keywords in output
- `skip_reason="text"`: Explanation for skipping certain commands
- `testable_note="text"`: Note about which commands are testable

**3. OVERRIDE annotation** - Correct command mismatches:

Use when `.prot` files reference incorrect command names.

```markdown
<!-- @PROGRAM_TEST_OVERRIDE: original_command="go run main.go" correct_command="go run go-channels.go" reason=".prot file uses main.go but actual file is go-channels.go" -->

[INSTRUCTOR::...]
```

Parameters:
- `original_command="cmd"`: Command as written in `.prot` file
- `correct_command="cmd"`: Correct command to execute
- `reason="text"`: Explanation for the override

**4. Normal testing** - No annotation needed:

Programs with deterministic output require no special annotation and are tested automatically

**Multi-command testing:**
- Parses and tests **ALL testable commands** from each `.prot` file
- Each command is executed sequentially with output comparison
- Test only passes if ALL commands succeed
- Detailed reporting shows status for each individual command
- Failed tests show which specific command(s) failed with error details

**Automatic cleanup:**
- Cleans up generated files before and after each test to ensure clean environment
- Removes database files (`.db`, `.sqlite`, `.sqlite3`)
- Removes log files (`.log`), temporary files (`.tmp`)
- Removes Python cache (`__pycache__`, `.pyc`)
- Prevents test failures caused by residual files from previous runs
- Ensures consistency between single program and full course testing

**Test output and reporting:**
- Displays total programs found and test pairs identified
- Shows programs passed, failed, and skipped (with detailed categories)
- For multi-command programs:
  - Lists each command with numbered index
  - Shows individual pass/fail status (✓ [PASS] or ✗ [FAIL])
  - Includes error details for failed commands
  - Separates tested commands from skipped commands
- Calculates success rate based on all programs
- Tracks execution time for each command and overall test
- Provides detailed failure reasons and manual testing requirements
- Generates both JSON and Markdown reports with categorized sections (Failed Tests, Skipped Tests, Passed Tests)

#### Prerequisites

**Important**: Program testing requires `itree.zip` to be built first. This directory is created during course building:

```bash
# Option 1: Complete build (tests all stages)
sedrila author /tmp/build

# Option 2: Beta stage only (faster, for quick testing)
sedrila author --include_stage beta /tmp/build

# Then run program tests
sedrila maintainer --check-programs
```

Without building first, the checker will report "Total Programs: 0" because it cannot find program files.

In GitHub Actions, **complete build** is automatically performed before testing to ensure full coverage.

#### Environment Requirements

Program testing requires the following environment:

**Required:**
- **Python**: 3.11 or higher
- **Go**: 1.23 or higher (for Go programs)
- **Built course**: `itree.zip` directory must exist in `altdir/`

**Python packages (Sedrila dependencies):**
- Core: argparse_subcommand, blessed, bottle, GitPython, Jinja2, Markdown, PyYAML, requests, rich
- Data/Scientific: matplotlib, numpy, pandas, Pygments
- Markdown: mdx_linkify

**Python packages (for example programs):**
- FastAPI programs: fastapi, pydantic, uvicorn
- Testing: pytest

In GitHub Actions, all dependencies are automatically installed. For local testing, ensure these packages are available in your environment.

#### CI/Batch Mode Features

Use the `--batch` flag to enable batch/CI-friendly output:

```bash
sedrila maintainer --check-programs --batch
```

- **Batch mode output** (`--batch`): Concise output suitable for automated testing
  - Without `--batch` (interactive): Detailed progress, colored output, real-time status
  - With `--batch` (CI): Concise output, only shows failures, error summary at end
- **Exit status**: Returns non-zero (1) when tests fail, zero (0) on success
- **Complete error list at end**: All failed tests are summarized at the end of output for quick error identification
- **Report generation**: JSON and Markdown reports are always generated for detailed analysis
- **Scheduled execution**: 
  - Link checking: Every Sunday at 03:00 UTC (`maintainer-linkchecker.yml`)
  - Program testing: Every Sunday at 03:30 UTC (`maintainer-programchecker.yml`)
  - Both workflows use the `--batch` flag for CI-friendly output

