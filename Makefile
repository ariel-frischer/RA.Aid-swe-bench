.PHONY: install run test clean format help clean-repos

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
	rm -rf repos

format:
	poetry run black .

evaluate:
	poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions
	poetry run python -m swebench.harness.run_evaluation \
		--dataset_name princeton-nlp/SWE-bench_Lite \
		--predictions_path predictions/lite-multi/all_preds.jsonl \
		--max_workers 1 --run_id 1
