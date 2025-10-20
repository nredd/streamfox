.PHONY: help install format lint type test smoke clean run all

# Virtual environment configuration
VENV := .venv
PYTHON := $(VENV)/bin/python
UV := ~/.local/bin/uv

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install all dependencies
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		$(UV) venv $(VENV); \
	fi
	@echo "Installing dependencies..."
	$(UV) sync --all-extras
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "To activate the virtual environment, run:"
	@echo "  source $(VENV)/bin/activate"

format:  ## Format code with ruff
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run ruff format .

lint:  ## Lint code with ruff
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run ruff check . --fix

type:  ## Type check with mypy
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run mypy src/streamfox

test:  ## Run tests with pytest
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run pytest -v --cov=src/streamfox --cov-report=term-missing

smoke:  ## Run all checks in parallel with tox (format, lint, type, test)
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run tox run-parallel

clean:  ## Clean all build artifacts, cache, logs, venv per .gitignore
	git clean -fXd
	@echo "✓ Cleaned all artifacts"

run:  ## Run streamfox CLI
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run streamfox

run-debug:  ## Run streamfox with debug logging
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run streamfox --debug

run-url:  ## Run streamfox with a specific URL (usage: make run-url URL=https://example.com/stream)
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run streamfox --url $(URL)

monitor:  ## Run in monitor mode
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run streamfox --monitor

all: format lint type test  ## Run full CI pipeline
	@echo ""
	@echo "✓ All checks passed!"
