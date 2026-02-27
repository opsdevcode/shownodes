.PHONY: install run clean format update lint install-dev

install:
	python3 -m pip install --system .
	# uv pip install --system .

install-dev:
	uv pip install --system -r requirements-dev.txt

run:
	$(MAKE) install
	clock &

clean:
	find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
	rm -rf *.egg-info
	rm -rf build dist
	rm -rf .pytest_cache .ruff_cache

lint:
	ruff check .

format: install-dev
	black .
	isort .

update:
	pur -r requirements.txt
	pur -r requirements-dev.txt
	$(MAKE) format
