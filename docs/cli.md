# CLI Reference

Complete reference for the Apte command-line interface.

## Synopsis

```bash
apte <command> [options] <target>
```

## Commands

| Command | Description |
|---------|-------------|
| `run` | Run tests |
| `eval` | Run evaluations |
| `live` | Start live reporter server |
| `tags list` | List tags in a session |

---

## apte run

Run tests from a session.

### Syntax

```bash
apte run <target> [options]
```

### Target Format

```
<module>:<session>[::SuiteName[::NestedSuite]]
```

| Part | Required | Description |
|------|----------|-------------|
| `module` | Yes | Python module path |
| `session` | Yes | Name of the `ApteSession` variable |
| `::SuiteName` | No | Filter to specific suite |

**Examples:**

```bash
apte run tests:session              # Run all tests
apte run myapp.tests:session        # Module in package
apte run tests:session::API         # Only API suite
apte run tests:session::API::Users  # Nested suite
```

### Options

#### Filtering Options

| Option | Short | Description |
|--------|-------|-------------|
| `::SuiteName` | - | Run only tests in specified suite (part of target) |
| `--keyword` | `-k` | Run tests matching keyword (substring match) |
| `--tag` | `-t` | Run tests with specified tag |
| `--no-tag` | - | Exclude tests with specified tag |
| `--last-failed` | `--lf` | Run only tests that failed last time |
| `--cache-clear` | - | Clear the test cache before running |
| `--collect-only` | - | List tests without running them |

#### Execution Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--concurrency` | `-n` | Number of parallel workers | 1 |
| `--exitfirst` | `-x` | Stop on first failure | false |
| `--no-capture` | `-s` | Show stdout/stderr during tests | false |
| `--app-dir` | - | Directory containing the module | . |

#### Output Options

| Option | Description |
|--------|-------------|
| `--no-color` | Disable colors (plain ASCII output) |
| `--no-log-file` | Disable writing to `.apte/last_run.log` |
| `--ctrf-output PATH` | Output CTRF JSON report to PATH |

---

## Filtering in Detail

### Suite Filter (::SuiteName)

The suite filter is part of the target, not a separate option. It filters tests to only those belonging to the specified suite and its children.

```bash
# Given this structure:
# session
# ├── API (suite)
# │   ├── Users (nested suite)
# │   │   ├── test_list_users
# │   │   └── test_create_user
# │   └── test_api_health
# └── test_standalone

# Run all API tests (including Users)
apte run tests:session::API
# Runs: test_api_health, test_list_users, test_create_user

# Run only Users tests
apte run tests:session::API::Users
# Runs: test_list_users, test_create_user

# Standalone tests are excluded when using suite filter
```

!!! note "Standalone Tests"
    Tests registered directly on the session (not in any suite) are excluded when using a suite filter.

### Keyword Filter (-k)

Match tests by substring in their name. Multiple `-k` flags use OR logic.

```bash
# Match test names containing "login"
apte run tests:session -k login
# Matches: test_login, test_login_failed, test_user_login

# Multiple keywords (OR logic)
apte run tests:session -k login -k logout
# Matches: test_login, test_logout, test_login_failed

# Works with parameterized tests (matches case IDs too)
apte run tests:session -k admin
# Matches: test_user[admin], test_permissions[admin-read]
```

!!! tip "Case Sensitivity"
    Keyword matching is case-sensitive. Use exact casing from your test names.

### Tag Filter (-t, --no-tag)

Filter by tags declared on tests, suites, or fixtures.

```bash
# Include tests with tag
apte run tests:session -t unit

# Multiple tags (OR logic)
apte run tests:session -t unit -t integration

# Exclude tests with tag
apte run tests:session --no-tag slow

# Combine include and exclude
apte run tests:session -t api --no-tag flaky
```

Tags are inherited:

- Tests inherit tags from their parent suite
- Tests inherit tags from fixtures they depend on (transitively)

### Last Failed (--lf)

Re-run only tests that failed in the previous run.

```bash
# First run - some tests fail
apte run tests:session
# Output: 8/10 passed, 2 failed

# Second run - only failed tests
apte run tests:session --lf
# Runs only the 2 failed tests
```

!!! warning "Behavior with Other Filters"
    When combined with other filters, `--lf` returns the **intersection**:

    - `--lf -t slow` → failed tests that have tag "slow"
    - If no failed tests match the filter, **0 tests run** (no fallback)

```bash
# Clear cache to run all tests again
apte run tests:session --cache-clear
```

---

## Combining Filters

All filters compose as **intersection** (AND logic between filter types).

```bash
# Suite AND keyword
apte run tests:session::API -k users
# Tests in API suite with "users" in name

# Suite AND keyword AND tag
apte run tests:session::API -k users -t slow
# Tests in API suite, with "users" in name, tagged "slow"

# Suite AND keyword AND tag AND last-failed
apte run tests:session::API -k users -t slow --lf
# Failed tests in API suite, with "users" in name, tagged "slow"
```

**Filter evaluation order:**

```
Collected tests
    → Suite filter (::SuiteName)
    → Keyword filter (-k)
    → Tag filter (-t, --no-tag)
    → Cache filter (--lf)
    → Final test list
```

---

## Execution Examples

### Development Workflow

```bash
# Run all tests
apte run tests:session

# Quick check - stop on first failure
apte run tests:session -x

# Re-run failures
apte run tests:session --lf

# Re-run failures, stop on first
apte run tests:session --lf -x
```

### CI/CD Workflow

```bash
# Full test suite, parallel
apte run tests:session -n 4

# Unit tests only
apte run tests:session -t unit -n 4

# Integration tests (might need sequential)
apte run tests:session -t integration

# Generate CTRF report for CI tools
apte run tests:session -n 4 --ctrf-output ctrf-report.json
```

### Debugging

```bash
# See output from tests
apte run tests:session -s

# Run specific test
apte run tests:session -k test_specific_function

# List what would run
apte run tests:session::API -k login --collect-only
```

### Working on a Feature

```bash
# Focus on one suite during development
apte run tests:session::API::Users -x

# Run related tests
apte run tests:session -k user -x

# Check everything still works
apte run tests:session
```

---

## apte eval

Run evaluations from a session.

`apte eval` is the eval-suite counterpart of `apte run`. It shares
the same target format, filters, capture flags and reporting options as
`run`; the differences are listed below.

### Syntax

```bash
apte eval <target> [options]
```

### Options

`apte eval` accepts every option from `apte run` (see above:
`-n/--concurrency`, `--collect-only`, `-x/--exitfirst`, `-s/--no-capture`,
`-q/--quiet`, `-v/--verbose`, `--show-logs`, `-t/--tag`, `--no-tag`,
`-k/--keyword`, `--lf`, `--cache-clear`, `--no-color`, `--ctrf-output`,
`--no-log-file`, `--app-dir`), plus one eval-only flag:

| Option | Description | Default |
|--------|-------------|---------|
| `--show-output` | Print `inputs` / `output` / `expected` for **every** case (failed cases always print these). | off |

### Examples

```bash
# Run all evals in a session
apte eval evals.session:session

# One specific suite
apte eval evals.session:session::helpdesk_struct

# One ticket by name
apte eval evals.session:session -k T001

# All cases tagged "cat:hardware"
apte eval evals.session:session --tag cat:hardware

# Re-run only the cases that failed last time
apte eval evals.session:session --lf

# Show the input/output of every case (not just failures)
apte eval evals.session:session --show-output
```

### Output

Each case prints one line:

```
✓   classify_ticket_struct[T011] (2ms) category_check.allowed=✓ summary_check.recall=1.00 …
```

After every suite, an aggregate-stats table summarizes the `Metric`
fields across cases (mean / p50 / p5 / p95). `Verdict` and `Reason`
fields don't appear in this table - only numeric `Metric` fields do.

Per-case markdown artifacts are written to
`.apte/results/<suite>_<timestamp>/<case-id>.md`, with the full
input, output, expected, and per-evaluator scores.

---

## Run history (recorded)

Every `run` / `eval` appends one entry to `.apte/history.jsonl`
(schema-versioned JSONL). History is **recorded from the first run** so the
data accumulates over time; dedicated commands to browse and compare runs
land in a future release.

Per-case eval detail (input, output, expected, evaluator scores) is written
to `.apte/results/<suite>_<timestamp>/<case-id>.md`.

---

## apte live

Start a persistent live reporter server for real-time test visualization.

### Syntax

```bash
apte live [options]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--port` | `-p` | Port to listen on | 8765 |

### Example

```bash
# Start the live server
apte live

# Start on a custom port
apte live -p 9000
```

The live server stays running and displays test results in real-time as you run tests in another terminal.

---

## apte tags list

List tags declared in a session.

### Syntax

```bash
apte tags list <target> [options]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--recursive` | `-r` | Show effective tags per test |
| `--app-dir` | - | Directory containing the module |

### Examples

```bash
# List all declared tags
apte tags list tests:session
# Output:
# api
# database
# integration
# slow
# unit

# Show tags per test (includes inherited)
apte tags list tests:session -r
# Output:
# Effective tags for 3 test(s):
#
#   API::test_api_call
#     tags: api, integration
#
#   API::test_db_query
#     tags: database, slow
#
#   test_simple
#     tags: unit
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed (or no tests collected) |
| 1 | One or more tests failed or errored |

---

## Environment

### Cache Location

Test results are cached in `.apte/cache.json` relative to the current directory.

```bash
# View cache location
ls .apte/

# Clear cache
apte run tests:session --cache-clear
# Or manually: rm -rf .apte/
```

### Module Resolution

By default, Apte looks for modules in the current directory. Use `--app-dir` to specify a different location:

```bash
# Module in src/ directory
apte run myapp.tests:session --app-dir src

# Module in project root (default)
apte run tests:session
```
