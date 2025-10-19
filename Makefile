.PHONY: help venv install format lint type test clean clean-venv run all activate

# Virtual environment configuration
VENV := .venv
PYTHON := $(VENV)/bin/python
UV := ~/.local/bin/uv

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv:  ## Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		$(UV) venv $(VENV); \
		echo "Virtual environment created at $(VENV)"; \
	else \
		echo "Virtual environment already exists at $(VENV)"; \
	fi

install: venv  ## Create venv and install all dependencies
	@echo "Installing dependencies..."
	$(UV) sync --all-extras
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "To activate the virtual environment, run:"
	@echo "  source $(VENV)/bin/activate"
	@echo ""
	@echo "Or use 'make activate' to see activation instructions"

activate:  ## Show how to activate the virtual environment
	@echo "To activate the virtual environment, run:"
	@echo ""
	@echo "  source $(VENV)/bin/activate"
	@echo ""
	@echo "To deactivate, run:"
	@echo "  deactivate"

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

test-fast:  ## Run tests without coverage
	@if [ ! -d "$(VENV)" ]; then echo "⚠️  Virtual environment not found. Run 'make install' first."; exit 1; fi
	$(UV) run pytest -v

clean:  ## Clean build artifacts (keeps venv)
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete
	@echo "✓ Cleaned build artifacts (virtual environment preserved)"

clean-venv:  ## Remove virtual environment
	rm -rf $(VENV)
	@echo "✓ Virtual environment removed"

clean-all: clean clean-venv  ## Clean everything including venv
	@echo "✓ Cleaned everything"

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

dev:  ## Install in development mode and show activation instructions
	@$(MAKE) install
	@echo ""
	@$(MAKE) activate

all: format lint type test  ## Run full CI pipeline
	@echo ""
	@echo "✓ All checks passed!"

# Show Python and package info
info:  ## Show Python and venv information
	@echo "Virtual Environment: $(VENV)"
	@if [ -d "$(VENV)" ]; then \
		echo "Status: ✓ Active"; \
		echo "Python: $$($(PYTHON) --version)"; \
		echo "Location: $$(which $(PYTHON) 2>/dev/null || echo 'Not in PATH')"; \
		echo ""; \
		echo "Installed packages:"; \
		$(UV) pip list; \
	else \
		echo "Status: ✗ Not created"; \
		echo "Run 'make install' to create and set up the virtual environment"; \
	fi
