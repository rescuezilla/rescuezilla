# Python linting and formatting using ruff
.PHONY: fmt lint python-fmt python-lint

# Python source directories to check
PYTHON_DIRS := src/apps/rescuezilla/rescuezilla/usr/lib/python3/dist-packages/rescuezilla \
               src/integration-test \
               src/scripts/manage-translations

# Format Python code using ruff
format: python-fmt
fmt: python-fmt
python-fmt:
	@echo "* Formatting Python code with ruff..."
	ruff format $(PYTHON_DIRS)

# Lint Python code using ruff
lint: python-lint
python-lint:
	@echo "* Linting Python code with ruff..."
	ruff check $(PYTHON_DIRS)

# Fix linting issues automatically where possible
fix: python-fix
python-fix:
	@echo "* Auto-fixing Python code with ruff..."
	ruff check --fix $(PYTHON_DIRS)

check: python-check
python-check:
	@echo "* Checking Python code formatting with ruff..."
	ruff format --check $(PYTHON_DIRS)
	@echo "* Checking Python code linting with ruff..."
	ruff check $(PYTHON_DIRS) 
