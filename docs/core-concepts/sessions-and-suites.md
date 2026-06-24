# Sessions & Suites

Apte organizes tests in a hierarchy: **Session** → **Suites** → **Tests**.

## ApteSession

A session is the root of your test hierarchy. You typically have one session per project, or one per major component in a monorepo.

```python
from apte import ApteSession

session = ApteSession()
```

### Session Options

```python
session = ApteSession(
    concurrency=4,  # Default parallelism (overridden by -n)
)
```

### Session-Level Tests

You can register tests directly on the session:

```python
@session.test()
async def test_something():
    assert True
```

These tests don't belong to any suite.

### Session Fixtures

Bind fixtures to the session with `bind()`:

```python
from apte import fixture

@fixture
def database():
    db = connect()
    yield db
    db.close()

session.bind(database)  # → SESSION scope
```

## ApteSuite

Suites group related tests together. They also define a scope boundary for fixtures.

```python
from apte import ApteSuite

api_suite = ApteSuite("API")
session.add_suite(api_suite)

@api_suite.test()
async def test_endpoint():
    assert True
```

### Suite Options

```python
api_suite = ApteSuite(
    "API",
    description="Integration tests for REST API",  # Optional documentation
    max_concurrency=2,          # Cap parallelism for this suite
    tags=["integration"],       # Tags inherited by all tests in suite
)
```

### Suite Fixtures

Bind fixtures to a suite with `bind()`:

```python
@fixture
def api_client():
    return Client()

api_suite.bind(api_client)  # → SUITE scope
```

## Nested Suites

Suites can contain other suites, creating a hierarchy:

```python
api_suite = ApteSuite("API")
users_suite = ApteSuite("Users")
orders_suite = ApteSuite("Orders")

api_suite.add_suite(users_suite)
api_suite.add_suite(orders_suite)

session.add_suite(api_suite)
```

This creates the structure:

```
Session
└── API
    ├── Users
    └── Orders
```

### Full Path

Each suite has a `full_path` property showing its position in the hierarchy:

```python
users_suite.full_path  # "API::Users"
orders_suite.full_path # "API::Orders"
```

### Fixture Inheritance

Child suites can access fixtures from parent suites:

```python
@fixture
def api_client():
    return Client()

api_suite.bind(api_client)  # → SUITE scope

@users_suite.test()
async def test_get_user(client: Annotated[Client, Use(api_client)]):
    # api_client is available here because Users is inside API
    pass
```

## Execution Order

1. Session fixtures are resolved once at start
2. Suites run in registration order
3. Within each suite:
    - Suite fixtures are resolved once
    - Tests run (potentially in parallel)
    - Suite fixtures are torn down
4. Session fixtures are torn down at end

Teardown follows LIFO order: children before parents.
