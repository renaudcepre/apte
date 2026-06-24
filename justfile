# justfile for Apte development
@default:
    echo "Hi ! Welcome to Apte !"
    just --list

# Run all linting and formatting
@lint:
    ruff format .
    ruff check --fix .
    uv run mypy apte

@fullcheck:
  ruff format --check . && ruff check .  # lint
  mypy --strict apte                  # types
  uv run pytest -vv                      # tests

# Run tests with verbose output
@test *options="":
    uv run pytest -vv {{ options }}

# Run tests with coverage
@test-cov *options="":
    uv run pytest -vv --cov=apte --cov-report=term {{ options }}

# Run tests with coverage and open browser
@test-cov-open *options="":
    uv run pytest -vv --cov=apte --cov-report=html {{ options }}
    python -m webbrowser htmlcov/index.html

# Development setup
setup:
    uv sync --dev
    pre-commit install

# Update pre-commit hooks to latest
update-hooks:
    pre-commit autoupdate

# Clean cache and temp files
clean:
    rm -rf .pytest_cache/
    rm -rf .ruff_cache/
    rm -rf htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} +

# Serve docs with hot reload
docs:
    uv run mkdocs serve --livereload --dirty

# Web Reporter
web-setup:
    cd web && npm install

web-dev:
    cd web && npm run dev

web-build:
    cd web && npm run build
