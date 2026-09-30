SHELL := /bin/sh
SNOW_CONNECTION ?= cashlessiq
PYTHON ?= python3.11
SQL_FOUNDATION := sql/00_account.sql sql/01_database.sql sql/02_core_tables.sql sql/03_docs_tables.sql sql/04_app_eval_tables.sql sql/05_spike_agent.sql

.PHONY: install setup teardown test lint generate-data policy-source data documents tools agent deploy eval

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

generate-data:
	$(PYTHON) -m data_gen.generate

policy-source:
	mkdir -p data_gen/output/policy
	curl -L --fail --silent --show-error \
		'https://www.newindia.co.in/assets/docs/know-more/health/arogya-sanjeevani/POLICY%20CLAUSES%20Arogya%20Sanjeevani.pdf' \
		-o data_gen/output/policy/newindia_arogya_sanjeevani_NIAHLIP25044V022425.pdf

data: generate-data policy-source
	snow sql --connection $(SNOW_CONNECTION) --filename sql/10_load_data.sql

documents:
	snow sql --connection $(SNOW_CONNECTION) --filename sql/20_extract_preauth.sql
	snow sql --connection $(SNOW_CONNECTION) --filename sql/21_policy_clauses.sql
	snow sql --connection $(SNOW_CONNECTION) --filename sql/22_search_service.sql
	snow sql --connection $(SNOW_CONNECTION) --filename sql/30_semantic_view.sql
	$(PYTHON) -m eval.phase2_acceptance --connection $(SNOW_CONNECTION)

tools:
	rm -f /tmp/cashlessiq.zip
	cd src && zip -q -r /tmp/cashlessiq.zip cashlessiq -x '*/__pycache__/*' '*.pyc'
	snow sql --connection $(SNOW_CONNECTION) --query "PUT file:///tmp/cashlessiq.zip @CASHLESSIQ.AI.CIQ_CODE_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
	snow sql --connection $(SNOW_CONNECTION) --filename sql/40_tools.sql

agent: tools
	snow sql --connection $(SNOW_CONNECTION) --filename sql/50_agent.sql

deploy:
	@echo "Phase 0 spike: verify snowflake.yml with CoCo, then run: snow streamlit deploy --connection $(SNOW_CONNECTION)"

eval:
	@echo "Phase 5 TODO: run the golden-set evaluator."
