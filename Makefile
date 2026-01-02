.PHONY: install test lint typecheck quality demo image

install:
	python -m pip install -e '.[dev]'

test:
	python -m pytest

lint:
	ruff check src tests examples
	ruff format --check src tests examples

typecheck:
	mypy src/forgemcp

quality: lint test typecheck

demo:
	forge demo

image:
	docker build --tag forgemcp:latest .

