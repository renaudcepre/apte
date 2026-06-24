# Running Tests

## Basic Command

```bash
apte run <module>:<session>
```

- `<module>` - Python module path (e.g., `tests`, `myapp.tests`)
- `<session>` - Name of the `ApteSession` variable in that module

## Filtering Tests

Apte provides multiple ways to filter which tests run. All filters can be combined.

### By Suite

Run only tests in a specific suite using `::SuiteName` syntax:

```bash
# Run tests in the "API" suite (and its children)
apte run tests:session::API

# Run tests in the nested "Users" suite under "API"
apte run tests:session::API::Users
```

### By Keyword (-k)

Run tests whose name contains a substring:

```bash
# Run tests containing "login" in their name
apte run tests:session -k login

# Multiple patterns use OR logic
apte run tests:session -k login -k logout
```

### By Tags (-t, --tag)

Run only tests with specific tags:

```bash
apte run tests:session --tag slow
apte run tests:session -t integration -t api   # OR logic
```

Exclude tests with specific tags:

```bash
apte run tests:session --no-tag flaky
```

### Re-run Failed Tests (--lf)

Only run tests that failed in the previous run:

```bash
apte run tests:session --lf
apte run tests:session --last-failed
```

Clear the failure cache:

```bash
apte run tests:session --cache-clear
```

### Combining Filters

All filters compose as intersection:

```bash
# Suite + keyword
apte run tests:session::API -k users

# Suite + keyword + tag
apte run tests:session::API -k users -t slow

# All filters together
apte run tests:session::API -k login -t integration --lf
```

## Execution Options

### Parallelism (-n)

Run tests concurrently:

```bash
apte run tests:session -n 4      # 4 workers
apte run tests:session -n 8      # 8 workers
```

### Exit on First Failure (-x)

Stop immediately when a test fails:

```bash
apte run tests:session -x
apte run tests:session --exitfirst
```

### Disable Output Capture (-s)

Show print statements and logs during test execution:

```bash
apte run tests:session -s
apte run tests:session --no-capture
```

### Verbosity Levels (-v)

Control output detail level. By default, only failures are shown with a live progress bar:

```bash
apte run tests:session           # Default: progress bar + failures only
apte run tests:session -v        # Show all test names + suite headers
apte run tests:session -vv       # Also show lifecycle (setup/teardown)
apte run tests:session -vvv      # Also show fixtures
```

| Level | Shows |
|-------|-------|
| 0 (default) | Progress bar, failures, summary |
| 1 (-v) | + All test names, suite headers |
| 2 (-vv) | + Session/suite setup and teardown |
| 3 (-vvv) | + Fixture setup and teardown |

### Collect Without Running

List tests without executing them:

```bash
apte run tests:session --collect-only
```

### Module Location

If your module is in a specific directory:

```bash
apte run tests:session --app-dir src
```

## Running with Coverage

Apte doesn't include a built-in coverage tool, but works seamlessly with [coverage.py](https://coverage.readthedocs.io/). Just run `apte` through `coverage run`:

```bash
# Collect coverage data
coverage run -m apte run tests:session

# Show report with missing lines
coverage report -m --include="app/*"

# Or generate an HTML report
coverage html --include="app/*"
```

If you use `uv`, prefix with `uv run`:

```bash
uv run coverage run -m apte run tests:session
uv run coverage report -m --include="app/*"
```

> **Tip:** Add `coverage` to your dev dependencies (`uv add --group dev coverage`).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed or errored |

## Tags Command

See all tags declared in a session:

```bash
apte tags list tests:session
```

Show effective tags per test (including inherited):

```bash
apte tags list tests:session -r
apte tags list tests:session --recursive
```
