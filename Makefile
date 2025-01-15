.PHONY: install run test clean format help clean-repos aider

help:
	@echo "Available commands:"
	@echo "  install          - Install project dependencies using Poetry"
	@echo "  run             - Run the main prediction script to generate new predictions"
	@echo "  test            - Run tests using pytest"
	@echo "  clean           - Remove Python cache files and bytecode"
	@echo "  clean-repos     - Remove all cached repositories from repos directory"
	@echo "  clean-predictions - Remove all prediction files and old directories (asks for confirmation)"
	@echo "  clean-logs      - Remove all files in logs directory while preserving the directory (asks for confirmation)"
	@echo "  format          - Format code using black"
	@echo "  check           - Run ruff linter with auto-fix enabled"
	@echo "  fix-predictions - Helper command when prediction files are borked/old adds missing fields"
	@echo "  reset-eval      - Reset prediction file evaluation fields (resolved and evaluated) to False"
	@echo "  eval            - Run evaluation on predictions in ra_aid_predictions directory"
	@echo "  eval-post       - Run detailed post-evaluation analysis (WIP/Legacy)"
	@echo "  aider           - Run aider with auto-lint in current directory"
	@echo "  install-pythons - Install all required Python versions using pyenv"
	@echo "  repo-sizes     - Show sizes of cached repositories and virtual environments"

install-pythons:
	pyenv install --skip-existing 3.5.10
	pyenv install --skip-existing 3.6.15
	pyenv rehash

install:
	poetry install

run:
	poetry run python -m swe_lite_ra_aid.main

test:
	poetry run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

clean-repos:
	rm -rf repos/*

clean-predictions:
	@echo "This will remove all prediction files and old directories. Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	rm -rf predictions/ra_aid_predictions/*
	rm -rf predictions/ra_aid_selected_predictions/*
	rm -rf predictions/old

clean-logs:
	@echo "This will remove all files in logs directory. Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	rm -rf logs/*

format:
	poetry run black .

check:
	poetry run ruff check --fix .

fix-predictions:
	poetry run python fix_prediction_files.py

reset-eval:
	poetry run python fix_prediction_files.py --reset-eval

eval:
	poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions

eval-post:
	poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions --post-eval

aider:
	aider --no-suggest-shell-commands --lint-cmd 'make check' --auto-lint

repo-sizes:
	@echo "Repository sizes (excluding .venv directories):"
	@du -sh repos/*/ 2>/dev/null | grep -v ".venv" || echo "No repositories found"
	@echo "Virtual environment sizes:"
	@du -sh repos/venvs/*/ 2>/dev/null || echo "No virtual environments found"
	@echo "Total size of repos/ directory:"
	@du -sh repos/
	@echo "Total size excluding virtual environments:"
	@repo_size=0; \
	for dir in repos/*/; do \
		if [[ $$dir != *"venvs"* ]]; then \
			size=$$(du -s "$$dir" | cut -f1); \
			repo_size=$$((repo_size + size)); \
		fi \
	done; \
	echo "$$(numfmt --to=iec-i --suffix=B $$repo_size)"
