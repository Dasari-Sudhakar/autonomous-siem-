.PHONY: help bootstrap up down logs ps train orchestrator attack-sim demo report clean

PYTHON  := .venv/bin/python
UVICORN := .venv/bin/uvicorn

help:
	@echo "Autonomous SIEM -- make targets"
	@echo ""
	@echo "  make bootstrap       Install all deps (run once on a fresh Ubuntu)"
	@echo "  make up              Start ELK stack (Elasticsearch + Kibana + Filebeat)"
	@echo "  make down            Stop ELK stack"
	@echo "  make logs            Tail container logs"
	@echo "  make ps              Show stack status"
	@echo "  make baseline        Generate ~15 min of benign auth traffic for ML training"
	@echo "  make train           Train Isolation Forest on the last 1h of data"
	@echo "  make orchestrator    Run FastAPI orchestrator (Ctrl-C to stop)"
	@echo "  make attack-self     Run Hydra against THIS host (solo testing without Kali)"
	@echo "  make report ID=N     Generate PDF for incident N from SQLite"
	@echo "  make clean           Stop stack and wipe ES data, model, responses DB"

bootstrap:
	./bootstrap.sh

up:
	cd docker && docker compose up -d
	@echo ""
	@echo "  Elasticsearch: http://localhost:9200"
	@echo "  Kibana:        http://localhost:5601 (wait ~30s for first boot)"

down:
	cd docker && docker compose down

logs:
	cd docker && docker compose logs -f --tail=100

ps:
	cd docker && docker compose ps

baseline:
	./attack/benign_traffic.sh 127.0.0.1 15

train:
	$(PYTHON) ml/train.py --hours 1 --out ml/isolation_forest.pkl

orchestrator:
	$(UVICORN) orchestrator.main:app --host 0.0.0.0 --port 8000

attack-self:
	./attack/ssh_brute.sh 127.0.0.1

report:
ifndef ID
	$(error Usage: make report ID=<incident_id>)
endif
	$(PYTHON) reports/generate.py --id $(ID)

clean:
	cd docker && docker compose down -v
	rm -f ml/isolation_forest.pkl
	rm -f /var/lib/siem/responses.db
	rm -rf reports/output
