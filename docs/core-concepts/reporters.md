# Reporters

Apte adapts its output automatically based on your environment.

## Display Modes

| Mode | When | Description |
|------|------|-------------|
| **Live** | Interactive terminal | Spinners, real-time updates, parallel test phases |
| **Rich** | CI, pipe, file | Colors, sequential output (no cursor manipulation) |
| **ASCII** | NO_COLOR, TERM=dumb | Plain text, no dependencies |

## Automatic Detection

Apte automatically selects the best reporter:

1. `NO_COLOR=1` → ASCII (respects the standard)
2. `TERM=dumb` → ASCII
3. Rich not installed → ASCII
4. `CI=true` → Rich (colors, no cursor manipulation)
5. Interactive terminal → Live
6. Pipe/file → Rich

## Force a Mode

```bash
# Disable colors (forces ASCII mode)
apte run demo:session --no-color
```

## Environment Variables

| Variable | Effect |
|----------|--------|
| `NO_COLOR=1` | Disables all colors |
| `CI=true` | Disables live mode (cursor manipulation) |
| `TERM=dumb` | Forces ASCII mode |

## Live Mode Features

When running in Live mode, you get:

- **Real-time test phases**: See tests progress through `waiting` → `setup` → `running` → `teardown`
- **Spinner animations**: Visual feedback for running tests
- **Log streaming**: Last log message displayed next to running tests
- **Suite teardown tracking**: See when suite fixtures are being torn down
- **Live summary line**: Current pass/fail counts updated in real-time

## Programmatic Usage

```python
from apte.api import run_session
from apte import ApteSession

session = ApteSession()

# Force ASCII mode (no colors)
run_session(
    session,
    force_no_color=True,
)
```

## Custom Reporters

You can create custom reporters by implementing the `PluginBase` interface:

```python
from apte.plugin import PluginBase
from apte.entities import TestResult, SessionResult

class MyReporter(PluginBase):
    def on_test_pass(self, result: TestResult) -> None:
        print(f"PASS: {result.name}")

    def on_test_fail(self, result: TestResult) -> None:
        print(f"FAIL: {result.name} - {result.error}")

    def on_session_complete(self, result: SessionResult) -> None:
        print(f"Done: {result.passed} passed, {result.failed} failed")

# Use your custom reporter
session = ApteSession(default_reporter=False)
session.use(MyReporter())
```

## CTRF Reporter (CI/CD Integration)

Apte includes a built-in [CTRF](https://ctrf.io) (Common Test Report Format) reporter for CI/CD integration. CTRF is a standardized JSON format supported by GitHub Actions, Slack, Jenkins, and other tools.

### Usage

```bash
# Generate CTRF report
apte run tests:session --ctrf-output ctrf-report.json

# Combine with parallel execution
apte run tests:session -n 4 --ctrf-output ctrf-report.json
```

### Output Format

The report includes:

- **Summary**: Test counts, duration, timestamps
- **Tests**: Name, status, duration, error messages, stack traces
- **Environment**: OS platform, git branch, commit SHA

### Example Output

```json
{
  "reportFormat": "CTRF",
  "specVersion": "0.0.0",
  "results": {
    "tool": { "name": "Apte", "version": "0.1.0" },
    "summary": {
      "tests": 10,
      "passed": 8,
      "failed": 2,
      "skipped": 0,
      "pending": 0,
      "other": 0,
      "start": 1733754600000,
      "stop": 1733754605000
    },
    "tests": [
      {
        "name": "test_login",
        "status": "passed",
        "duration": 150,
        "suite": ["API", "Auth"]
      },
      {
        "name": "test_invalid_token",
        "status": "failed",
        "duration": 50,
        "message": "AssertionError: Expected 401",
        "trace": "Traceback ..."
      }
    ],
    "environment": {
      "osPlatform": "linux",
      "branchName": "main",
      "commit": "abc123"
    }
  }
}
```

### Status Mapping

| Apte Status | CTRF Status | rawStatus |
|---------------|-------------|-----------|
| passed | `passed` | - |
| failed | `failed` | - |
| skipped | `skipped` | - |
| xfail | `failed` | `xfail` |
| xpass | `failed` | `xpass` |
| fixture error | `failed` | `error` |
| timeout | `failed` | `timeout` |

### Programmatic Usage

```python
from pathlib import Path
from apte.reporting.ctrf import CTRFReporter

session = ApteSession()
session.use(CTRFReporter(output_path=Path("ctrf-report.json")))
```
