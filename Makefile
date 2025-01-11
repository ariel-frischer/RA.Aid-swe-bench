.PHONY: install run test clean format help clean-repos aider

help:
	@echo "Available commands:"
	@echo "  install  - Install project dependencies using Poetry"
	@echo "  run      - Run the main prediction script"
	@echo "  test     - Run tests using pytest"
	@echo "  clean    - Remove Python cache files and predictions"
	@echo "  format   - Format code using black (requires black to be installed)"

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
	rm -f ra_aid_predictions.jsonl

clean-repos:
	rm -rf repos/*

clean-predictions:
	@echo "This will remove all prediction files and old directories. Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	rm -rf predictions/ra_aid_predictions/*.json
	rm -rf predictions/ra_aid_predictions/*.jsonl
	rm -rf predictions/ra_aid_predictions/*.txt
	rm -rf predictions/ra_aid_selected_predictions/*.jsonl
	rm -rf predictions/old

format:
	poetry run black .

check:
	poetry run ruff check --fix .

add-model-name:
	poetry run python add_model_name.py

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
