
# --- AUTOMATIC CONFIGURATION ---
# Detects '26.4.0' from 'feature/26.4.0/QWS-0301'
CURRENT_BRANCH := $(shell git symbolic-ref --short HEAD)
REL_VER := $(shell echo $(CURRENT_BRANCH) | cut -d'/' -f2)

RELEASE_BRANCH = release/$(REL_VER)
MASTER_BRANCH = master

.PHONY: to-release to-master check-clean done-with-feature test test-unit lint typecheck check commit-close-story prime-agent prime-lint-mechanic feature-branch


# --- QUALITY ---

test:
	source .venv/bin/activate && pytest qws_graph/tests/unit/ -v

test-unit:
	source .venv/bin/activate && pytest tests/unit/ -v

lint:
	source .venv/bin/activate && ruff check .

typecheck:
	source .venv/bin/activate && mypy --strict .

check: lint typecheck test

# --- GIT WORKFLOW ---

# Internal helper to check for uncommitted changes
check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Your working directory is dirty. Commit or stash changes."; \
		exit 1; \
	fi

# 1. Sync feature, merge to release, and return
to-release: check-clean
	@echo "Syncing $(CURRENT_BRANCH) with remote..."
	git push origin $(CURRENT_BRANCH)
	@echo "Merging into $(RELEASE_BRANCH)..."
	git checkout $(RELEASE_BRANCH)
	git pull origin $(RELEASE_BRANCH)
	git merge $(CURRENT_BRANCH)
	git push origin $(RELEASE_BRANCH)
	@echo "Done! Returning to $(CURRENT_BRANCH)..."
	git checkout $(CURRENT_BRANCH)

# 2. Merge Release into Master
to-master: check-clean
	@echo "Finalizing Release $(REL_VER) into Master..."
	git checkout $(MASTER_BRANCH)
	git pull origin $(MASTER_BRANCH)
	git merge $(RELEASE_BRANCH)
	git push origin $(MASTER_BRANCH)
	git checkout $(RELEASE_BRANCH)

# 3b. Create feature branch from release branch
# Usage: make feature-branch STORY=QWS-0804
feature-branch:
	@[ -n "$(STORY)" ] || (echo "ERROR: STORY required. Usage: make feature-branch STORY=QWS-0804"; exit 1)
	git checkout $(RELEASE_BRANCH)
	git pull origin $(RELEASE_BRANCH)
	git checkout -b feature/$(REL_VER)/$(STORY)

# 3c. Prime agent guards before spawning lead-engineer (arms sentinel + trackers from call #1)
# Usage: make prime-agent
prime-agent:
	@mkdir -p /tmp/agent-read-tracker /tmp/agent-discovery-tracker /tmp/circuit-breaker
	@echo "implement-story" > /tmp/agent-current-command.txt
	@rm -f /tmp/agent-step8-committed.txt
	@echo "Agent guards primed. Safe to spawn lead-engineer."

prime-lint-mechanic:
	@mkdir -p /tmp/agent-read-tracker /tmp/agent-discovery-tracker /tmp/circuit-breaker
	@echo "lint-mechanic" > /tmp/agent-current-command.txt
	@echo "Lint-mechanic guards primed."

# 4. Commit story status update + arm agent phase gate (atomic — sentinel cannot be skipped)
# Usage: make commit-story-status STORY=QWS-0801
#        make commit-story-status STORY=QWS-0801 MSG="custom commit message"
commit-story-status:
	@[ -n "$(STORY)" ] || (echo "ERROR: STORY required. Usage: make commit-story-status STORY=QWS-0801"; exit 1)
	@echo "done" > /tmp/agent-step8-committed.txt
	git add -u
	git commit -m "$(if $(MSG),$(MSG),status($(STORY)): READY → TESTING)" || echo "WARN: nothing to commit (already committed?)"
	@echo "Phase gate armed. Agent hard stop active."

# 4b. Commit story closure
# Usage: make commit-close-story STORY=QWS-0801
commit-close-story:
	@[ -n "$(STORY)" ] || (echo "ERROR: STORY required. Usage: make commit-close-story STORY=QWS-0801"; exit 1)
	git add -u
	git commit -m "$(if $(MSG),$(MSG),close($(STORY)): story closed)"

# 5. Optional: Delete feature branch after successful merge
done-with-feature:
	@read -p "Delete branch $(CURRENT_BRANCH)? (y/n): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		git checkout $(RELEASE_BRANCH); \
		git branch -d $(CURRENT_BRANCH); \
		git push origin --delete $(CURRENT_BRANCH); \
	fi

