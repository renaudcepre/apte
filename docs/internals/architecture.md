# Architecture Overview

Apte follows a Ports & Adapters (hexagonal) architecture, separating the domain logic from external interfaces.

## Layers

```
┌─────────────────────────────────────────────────────────┐
│                     Adapters                            │
│  ┌─────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CLI   │  │ Loader │  │ Reporters│  │  Plugins │   │
│  └────┬────┘  └────┬───┘  └────┬─────┘  └────┬─────┘   │
└───────┼────────────┼───────────┼─────────────┼─────────┘
        │            │           │             │
        ▼            ▼           ▼             ▼
┌─────────────────────────────────────────────────────────┐
│                    Ports (API)                          │
│  run_session()  collect_tests()  list_tags()            │
│  load_session()                                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                      Domain                             │
│  ApteSession  TestRunner  Collector  FixtureContainer        │
│  ApteSuite    EventBus                               │
└─────────────────────────────────────────────────────────┘
```

## Domain Layer

The core test execution logic, independent of how tests are discovered or results are displayed.

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `ApteSession` | `core/session.py` | Test session container |
| `ApteSuite` | `core/suite.py` | Test grouping |
| `TestRunner` | `core/runner.py` | Test execution |
| `Collector` | `core/collector.py` | Test discovery |
| `FixtureContainer` | `di/container.py` | Fixture resolution |
| `EventBus` | `events/bus.py` | Event dispatching |

## Ports Layer (`apte/api.py`)

The public API for programmatic use. These functions don't depend on any specific adapter.

```python
from apte import ApteSession, run_session, collect_tests, list_tags

session = ApteSession()
# ... define tests ...

# Run tests
success = run_session(session, concurrency=4, exitfirst=True)

# Collect without running
items = collect_tests(session, include_tags={"unit"})

# List declared tags
tags = list_tags(session)
```

### Loader (`apte/loader.py`)

Loads sessions from module paths:

```python
from apte import load_session, LoadError

try:
    session = load_session("mymodule:session", app_dir="src")
except LoadError as e:
    print(f"Failed to load: {e}")
```

## Adapters Layer

### CLI (`apte/cli/`)

Entry point for command-line usage. Parses arguments and calls the API.

```bash
apte run module:session [options]
apte tags list module:session
```

The CLI is a thin wrapper that:
1. Parses arguments (argparse)
2. Uses `load_session()` to get the session
3. Calls `run_session()` with options
4. Returns exit code (0/1)

### Reporters

Plugins that subscribe to events and format output:
- `RichReporter` - Rich terminal output
- `AsciiReporter` - Plain text fallback
- `CTRFReporter` - JSON for CI/CD

### Plugins

Custom extensions that hook into the event bus:
- `CachePlugin` - Last-failed mode
- `TagFilterPlugin` - Tag filtering
- `SuiteFilterPlugin` - Suite filtering
- `KeywordFilterPlugin` - Keyword filtering

## Module Structure

```
apte/
├── core/           # Domain: Session, Suite, Runner, Collector
├── di/             # Domain: FixtureContainer, Markers (Use), Validation
├── entities/       # Domain: Dataclasses (Fixture, TestItem, TestResult)
├── events/         # Domain: Event bus
├── execution/      # Domain: AsyncBridge, Capture, Context
├── fixtures/       # Domain: Built-in fixtures (caplog, mocker)
│
├── api.py          # Ports: Public API
├── loader.py       # Ports: Module loading
│
├── cli/            # Adapter: Command-line interface
├── reporting/      # Adapter: Reporters
├── cache/          # Adapter: CachePlugin
├── tags/           # Adapter: TagFilterPlugin
└── filters/        # Adapter: Suite/Keyword filters
```

## See Also

- [Event Bus](event-bus.md) - Event dispatching internals
- [Dependency Injection](dependency-injection.md) - Fixture resolution
- [Plugins](plugins.md) - Writing plugins
