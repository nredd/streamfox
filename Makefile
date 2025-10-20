.PHONY: help install format lint type test smoke clean run

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

format: install  ## Format code with ruff
	$(UV) run ruff format .

lint: install  ## Lint code with ruff
	$(UV) run ruff check . --fix

type: install  ## Type check with mypy
	$(UV) run mypy src/streamfox

test: install  ## Run tests with pytest
	$(UV) run pytest -v --cov=src/streamfox --cov-report=term-missing

smoke: install  ## Run all checks in parallel with tox (format, lint, type, test)
	$(UV) run tox run-parallel

clean:  ## Clean all build artifacts, cache, logs, venv per .gitignore
	git clean -fXd
	@echo "✓ Cleaned all artifacts"

run: install  ## Run streamfox CLI
	$(UV) run streamfox

run-debug: install  ## Run streamfox with debug logging
	$(UV) run streamfox --debug

run-url: install  ## Run streamfox with a specific URL (usage: make run-url URL=https://example.com/stream)
	$(UV) run streamfox --url $(URL)

monitor: install  ## Run in monitor mode
	$(UV) run streamfox --monitor
