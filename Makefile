.PHONY: install run clean format lint install-dev test

install:
	uv pip install --system .

install-dev:
	uv pip install --system -e ".[dev]"

run:
	$(MAKE) install
	shownodes --help

clean:
	find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
	rm -rf *.egg-info
	rm -rf build dist
	rm -rf .pytest_cache .ruff_cache

lint:
	ruff check .

format:
	black .
	isort .

test:
	pytest
