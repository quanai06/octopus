.PHONY: install test lint type check benchmark all

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .

type:
	mypy src

benchmark:
	pytest -q tests/benchmark

# Full local gate: run before every commit / in CI.
check: lint type test

all: install check
