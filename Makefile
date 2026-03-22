.PHONY: test lint format typecheck dev clean

dev:
	pip install -e ".[dev]"

test:
	python -m pytest tests/

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy src/ wickerman_plugins/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

ci: lint test
