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
  
#### Program testing configuration

Testing strategies for different program categories. This allows flexible handling of various program
types without modifying code.

**Configuration sections:**

**1. SKIP Section** - Programs requiring manual testing:
- Programs with non-deterministic output (memory addresses, concurrent execution order, timestamps)
- Programs requiring interactive input
- Programs with environment-specific output (e.g., `sys.path` varies across machines)
- Shell redirection that cannot be reliably automated (e.g., `>/tmp/a` cannot be distinguished from arguments)
- Example configuration:
  ```yaml
  skip_programs:
    - program_name: "go-waitgroup"
      reason: "Concurrent execution order is non-deterministic"
      manual_test_required: true
  ```

**2. Partial Skip Section** - Programs with mixed testability:
- Some commands within the program are testable, others require manual verification
- Handles programs with Traceback output variations, non-deterministic output, interactive requirements, or error demonstrations
- Configuration specifies which command patterns to skip and provides reasons
- Currently empty as programs are either fully testable or require complete manual testing
- Example configuration for future use:
  ```yaml
  partial_skip_programs:
    # Currently empty - programs are either fully testable or require complete manual testing
    # Example configuration for future use:
    # - program_name: "example_program"
    #   skip_commands_with:
    #     - "Traceback (most recent call last):"
    #     - "MemoryError"
    #   skip_reason: "Different stack depths lead to inconsistent Traceback output"
    #   testable_note: "Other commands without error demonstrations can be automatically tested"
  ```

**3. Command Override Section** - Correct command mismatches:
- Maps incorrect commands in `.prot` files to correct program filenames
- Useful when `.prot` files reference generic names but actual files have specific names
- Example:
  ```yaml
  command_override:
    - program_name: "go-channels"
      original_command: "go run main.go"
      correct_command: "go run go-channels.go"
      reason: ".prot file uses main.go but actual file is go-channels.go"
  ```

**4. Normal Test Section** - Fully automated testing:
- Programs with deterministic output
- No special handling required
- Simply list program names for documentation purposes

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

