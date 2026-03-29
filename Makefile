.PHONY: up down logs restart build clean reset status report \
        cc recon exploit detect remediate monitor

# ── Full stack ────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

build:
	docker compose build --no-cache

# Tear down everything including volumes (full wipe)
clean:
	docker compose down -v --remove-orphans

# Stop + wipe volumes, then bring back up fresh
reset: clean
	docker compose up -d --build

# ── Status ────────────────────────────────────────────────────
status:
	@echo ""
	@echo "=== SecuNet Container Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Kali CC tools ==="
	@docker exec secunet-command-center nmap --version 2>/dev/null | head -1 || echo "CC not running"
	@echo ""

# ── Report ────────────────────────────────────────────────────
report:
	@echo "Generating mission report..."
	@curl -s http://localhost:8001/report | python3 -m json.tool

# ── Per-service logs ──────────────────────────────────────────
cc:
	docker compose logs -f command-center

recon:
	docker compose logs -f recon-agent

exploit:
	docker compose logs -f exploit-agent

detect:
	docker compose logs -f detect-agent

remediate:
	docker compose logs -f remediate-agent

monitor:
	docker compose logs -f monitor-agent
