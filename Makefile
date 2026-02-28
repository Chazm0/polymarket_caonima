.PHONY: help setup migrate ingest track refresh collect export

help:
	@echo "Targets:"
	@echo "  make setup              - Create venv + install editable"
	@echo "  make migrate            - Apply migrations"
	@echo "  make ingest PAGES=1     - Ingest markets (optional EVENT_ID=123 LIMIT=1000)"
	@echo "  make track SESSION=... IDS=1,2,3"
	@echo "  make refresh            - Refresh ended flags"
	@echo "  make collect ITERS=0    - Collect orderbooks (optional BATCH=50 TOP_N=10 LOOP=2)"
	@echo "  make export ARGS='--market-id 123 --expected-seconds 2'"

setup:
	./scripts/dev_setup.sh

migrate:
	./scripts/migrate.sh

ingest:
	@PAGES=$(or $(PAGES),1) LIMIT=$(or $(LIMIT),1000) EVENT_ID=$(EVENT_ID) ./scripts/ingest_markets.sh

track:
	@if [ -z "$(SESSION)" ] || [ -z "$(IDS)" ]; then echo "Usage: make track SESSION=manual IDS=123,456"; exit 2; fi
	./scripts/track_markets.sh "$(SESSION)" "$(IDS)"

refresh:
	./scripts/refresh_ended.sh

collect:
	@BATCH=$(BATCH) TOP_N=$(TOP_N) LOOP=$(LOOP) PER_BATCH_SLEEP=$(or $(PER_BATCH_SLEEP),0.1) ITERS=$(or $(ITERS),0) ./scripts/collect_orderbooks.sh

export:
	@if [ -z "$(ARGS)" ]; then echo "Usage: make export ARGS='--market-id 123 --expected-seconds 2'"; exit 2; fi
	./scripts/export_dataset.sh $(ARGS)