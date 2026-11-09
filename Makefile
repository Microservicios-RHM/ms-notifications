.PHONY: test test-ci

test:
	python -m pytest

test-ci: test
