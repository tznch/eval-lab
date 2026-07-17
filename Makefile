.PHONY: setup download download-sciq download-realworld prepare prepare-sciq prepare-portfolio prepare-dataset datasets-list clean-results stop-servers promptfoo-tests server smoke-judge smoke-target eval-promptfoo eval-promptfoo-ifeval eval-deepeval eval-ragas eval-all lab lab-portfolio portfolio dashboard export-report dashboard-serve profile-export profile-import tools-update test

VENV := .venv/bin
# Default sample dataset id; override with EVAL_DATASET=<id> from `make datasets-list`
EVAL_DATASET ?= sciq

setup:
	uv venv .venv --clear 2>/dev/null || uv venv .venv
	uv pip install -e ".[dev]" --python .venv/bin/python
	npm install -g promptfoo || true

download:
	$(VENV)/python scripts/download_uda_qa.py --config feta

download-sciq:
	$(VENV)/python scripts/download_sciq.py --split validation --limit 200

stop-servers:
	bash scripts/stop_model_servers.sh

prepare: download
	$(VENV)/python scripts/prepare_samples.py --config feta --limit 50
	$(VENV)/python scripts/prepare_samples.py --config nq --limit 50

prepare-sciq: download-sciq
	$(VENV)/python scripts/prepare_samples.py --config sciq --limit 100

datasets-list:
	$(VENV)/python scripts/dataset_cli.py list

prepare-dataset:
	$(VENV)/python scripts/dataset_cli.py prepare --dataset $(DATASET) $(if $(LIMIT),--limit $(LIMIT),)

clean-results:
	$(VENV)/python scripts/clean_results.py

download-realworld:
	$(VENV)/python scripts/download_realworld.py all --limit 500

prepare-portfolio: download-sciq download-realworld
	$(VENV)/python scripts/prepare_samples.py --config sciq --limit 25
	$(VENV)/python scripts/prepare_samples.py --config financial_qa --limit 25
	$(VENV)/python scripts/prepare_samples.py --config ecommerce_faq --limit 25
	$(VENV)/python scripts/prepare_samples.py --config bitext_intent --limit 25

# Requires MODEL=<id> with {ID}_BASE_URL / {ID}_MODEL_NAME (or TARGET_MODEL_*) in .env
portfolio:
	@test -n "$(MODEL)" || (echo "Set MODEL=<id> (configured via HF import / .env)"; exit 1)
	bash scripts/run_portfolio_evals.sh --model $(MODEL) $(if $(filter 1,$(SKIP_SETUP)),--skip-setup,)

lab-portfolio:
	@test -n "$(MODEL)" || (echo "Set MODEL=<id>"; exit 1)
	bash scripts/run_lab.sh --model $(MODEL) --portfolio

PROMPTFOO_LIMIT ?= 25

promptfoo-tests:
	$(VENV)/python scripts/jsonl_to_promptfoo.py --config $(EVAL_DATASET) --limit $(PROMPTFOO_LIMIT)

# Requires LLAMA_HF_MODEL=org/Model-GGUF:quant
server:
	@if ss -tln 2>/dev/null | grep -q ':8080 '; then \
		echo "llama-server already running on :8080 (skip make server)"; \
		exit 0; \
	fi
	bash models/start-server.sh

smoke-target:
	$(VENV)/python scripts/smoke_target.py

smoke-judge:
	$(VENV)/python scripts/smoke_judge.py

smoke-judge-glm:
	JUDGE_PROVIDER=glm $(VENV)/python scripts/smoke_judge.py

smoke-judge-openrouter:
	JUDGE_PROVIDER=openrouter $(VENV)/python scripts/smoke_judge.py

eval-promptfoo: promptfoo-tests
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/run_promptfoo_eval.py

# Instruction-following mini-track (Promptfoo only)
eval-promptfoo-ifeval:
	$(VENV)/python scripts/run_promptfoo_ifeval.py

eval-deepeval:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/pytest eval/deepeval/test_uda_qa.py -v --tb=short

eval-ragas:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python eval/ragas/run.py --config $(EVAL_DATASET) --limit 50

# MODEL=<id> required (comma-separated for multiple)
MODEL ?=

# Full pipeline: prepare + all frameworks × target models
eval-all:
	@test -n "$(MODEL)" || (echo "Set MODEL=<id>[,id2]"; exit 1)
	bash scripts/run_all_evals.sh --model $(MODEL)

# ONE command: servers + eval-all + dashboard
lab:
	@test -n "$(MODEL)" || (echo "Set MODEL=<id>"; exit 1)
	bash scripts/run_lab.sh --model $(MODEL)

dashboard:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/build_dashboard.py

export-report:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/export_report.py

dashboard-serve:
	bash scripts/serve_dashboard.sh

# profile-export: NAME=... [OUT=path/to/profile.yaml]
profile-export:
	$(VENV)/python scripts/profile_cli.py export --name $(NAME) $(if $(OUT),--out $(OUT),)

# profile-import: PROFILE=path/to/profile.yaml
profile-import:
	$(VENV)/python scripts/profile_cli.py import --profile $(PROFILE)

tools-update:
	bash scripts/tools_update.sh

test:
	$(VENV)/pytest tests/ -v
