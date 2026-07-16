.PHONY: setup download download-sciq download-bonsai download-qwen27 download-qwen36q4 download-realworld prepare prepare-sciq prepare-portfolio prepare-dataset datasets-list clean-results stop-servers promptfoo-tests server server-bonsai server-qwen27 smoke-judge smoke-target smoke-bonsai eval-promptfoo eval-promptfoo-ifeval eval-deepeval eval-ragas eval-all lab lab-portfolio portfolio portfolio-qwen27 dashboard export-report dashboard-serve profile-export profile-import tools-update

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

download-bonsai:
	$(VENV)/python scripts/download_bonsai.py

download-qwen27:
	$(VENV)/python scripts/download_qwen27.py

download-qwen36q4:
	$(VENV)/python scripts/download_qwen36q4.py

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

portfolio:
	bash scripts/run_portfolio_evals.sh $(if $(MODEL),--model $(MODEL),) $(if $(filter 1,$(SKIP_SETUP)),--skip-setup,)

portfolio-bonsai-t07:
	TARGET_TEMPERATURE=0.7 $(MAKE) portfolio MODEL=bonsai SKIP_SETUP=$(SKIP_SETUP)

portfolio-qwen27-t02:
	TARGET_TEMPERATURE=0.2 $(MAKE) portfolio-qwen27 SKIP_SETUP=$(SKIP_SETUP)

portfolio-qwen27:
	bash scripts/run_comparable_qwen_portfolio.sh $(if $(filter 1,$(SKIP_SETUP)),--skip-setup,)

lab-portfolio:
	bash scripts/run_lab.sh $(if $(MODEL),--model $(MODEL),) --portfolio

PROMPTFOO_LIMIT ?= 25

promptfoo-tests:
	$(VENV)/python scripts/jsonl_to_promptfoo.py --config $(EVAL_DATASET) --limit $(PROMPTFOO_LIMIT)

server:
	@if ss -tln 2>/dev/null | grep -q ':8080 '; then \
		echo "llama-server already running on :8080 (skip make server)"; \
		exit 0; \
	fi
	bash models/start-server.sh

server-bonsai:
	@if ss -tln 2>/dev/null | grep -q ':8081 '; then \
		echo "Bonsai server already running on :8081 (skip)"; \
		exit 0; \
	fi
	bash models/start-bonsai-server.sh

server-qwen27:
	@if ss -tln 2>/dev/null | grep -q ':8082 '; then \
		echo "Qwen server already running on :8082 (skip)"; \
		exit 0; \
	fi
	bash models/start-qwen27-server.sh

smoke-target:
	$(VENV)/python scripts/smoke_target.py

smoke-bonsai:
	$(VENV)/python scripts/smoke_bonsai.py

smoke-judge:
	$(VENV)/python scripts/smoke_judge.py

smoke-judge-glm:
	JUDGE_PROVIDER=glm $(VENV)/python scripts/smoke_judge.py

smoke-judge-openrouter:
	JUDGE_PROVIDER=openrouter $(VENV)/python scripts/smoke_judge.py

# Compare Gemma (:8080) vs Bonsai Q1 (:8081) — both servers must be running
eval-promptfoo: promptfoo-tests
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/run_promptfoo_eval.py

# Instruction-following mini-track (Promptfoo only)
eval-promptfoo-ifeval:
	$(VENV)/python scripts/run_promptfoo_ifeval.py

eval-deepeval:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/pytest eval/deepeval/test_uda_qa.py -v --tb=short

eval-ragas:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python eval/ragas/run.py --config $(EVAL_DATASET) --limit 50

# MODEL=gemma|bonsai|gemma,bonsai (default: both)
MODEL ?=

# Full pipeline: prepare + all frameworks × all target models
eval-all:
	bash scripts/run_all_evals.sh $(if $(MODEL),--model $(MODEL),)

# ONE command: servers + eval-all + dashboard (blocks on :3000)
lab:
	bash scripts/run_lab.sh $(if $(MODEL),--model $(MODEL),)

dashboard:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/build_dashboard.py

export-report:
	EVAL_DATASET=$(EVAL_DATASET) $(VENV)/python scripts/export_report.py

dashboard-serve:
	bash scripts/serve_dashboard.sh

# profile-export: NAME=... [OUT=path/to/profile.yaml]
profile-export:
	$(VENV)/python scripts/profile_cli.py export --name $(NAME) $(if $(OUT),--out $(OUT),)

# profile-import: PROFILE=profiles/examples/bonsai-sciq-t07.yaml
profile-import:
	$(VENV)/python scripts/profile_cli.py import --profile $(PROFILE)

tools-update:
	bash scripts/tools_update.sh

test:
	$(VENV)/pytest tests/ -v
