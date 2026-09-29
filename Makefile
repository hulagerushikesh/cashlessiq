SHELL := /bin/sh
SNOW_CONNECTION ?= cashlessiq
PYTHON ?= python3.11
SQL_FOUNDATION := sql/00_account.sql sql/01_database.sql sql/02_core_tables.sql sql/03_docs_tables.sql sql/04_app_eval_tables.sql

.PHONY: install setup teardown test lint data deploy eval

install:
	$(PYTHON) -m pip install -e ".[dev]"

setup:
	@for file in $(SQL_FOUNDATION); do \
		echo "Applying $$file"; \
		snow sql --connection $(SNOW_CONNECTION) --filename "$$file" || exit 1; \
	done

teardown:
	snow sql --connection $(SNOW_CONNECTION) --filename sql/99_teardown.sql

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

data:
	@echo "Phase 1 TODO: generate and load deterministic synthetic data."

deploy:
	@echo "Phase 0 spike: verify snowflake.yml with CoCo, then run: snow streamlit deploy --connection $(SNOW_CONNECTION)"

eval:
	@echo "Phase 5 TODO: run the golden-set evaluator."

