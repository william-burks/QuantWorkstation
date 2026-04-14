COMPOSE_FILE := docker-compose.neo4j.yml
SERVICE := qws-neo4j

.PHONY: help neo4j-up neo4j-down neo4j-restart neo4j-logs neo4j-status seed

.DEFAULT_GOAL := help

help:
	@echo "Neo4j local lifecycle targets:"
	@echo "  make neo4j-up       # Start local Neo4j in detached mode"
	@echo "  make neo4j-down     # Stop and remove local Neo4j stack"
	@echo "  make neo4j-restart  # Restart local Neo4j stack"
	@echo "  make neo4j-logs     # Show recent Neo4j logs"
	@echo "  make neo4j-status   # Show Neo4j container status"
	@echo "  make seed           # Seed demo graph + ResearchTarget node"

neo4j-up:
	docker compose -f $(COMPOSE_FILE) up -d --wait $(SERVICE)

neo4j-down:
	docker compose -f $(COMPOSE_FILE) down

neo4j-restart: neo4j-down neo4j-up

neo4j-logs:
	docker compose -f $(COMPOSE_FILE) logs --tail=200 $(SERVICE)

neo4j-status:
	docker compose -f $(COMPOSE_FILE) ps $(SERVICE)

seed: neo4j-up
	cd .. && source .venv/bin/activate && qw seed --demo && qw seed --targets

