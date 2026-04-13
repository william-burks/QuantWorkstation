
# --- AUTOMATIC CONFIGURATION ---
# Detects '26.4.0' from 'feature/26.4.0/QWS-0301'
CURRENT_BRANCH := $(shell git symbolic-ref --short HEAD)
REL_VER := $(shell echo $(CURRENT_BRANCH) | cut -d'/' -f2)

RELEASE_BRANCH = release/$(REL_VER)
MASTER_BRANCH = master

.PHONY: to-release to-master check-clean done-with-feature test test-unit test-integration test-all lint typecheck check verify commit-impl commit-test commit-push-qa commit-close-story prime-agent prime-lint-mechanic feature-branch arm-verify-gate arm-qa-gate arm-close-epic-gate


# --- QUALITY ---

test:
	source .venv/bin/activate && pytest qws_graph/tests/unit/ -v --tb=long

test-unit:
	source .venv/bin/activate && pytest tests/unit/ -v --tb=long

test-integration:
	source .venv/bin/activate && pytest qws_graph/tests/integration/ -v --tb=long

test-all: test test-unit

lint:
	source .venv/bin/activate && ruff check . --fix && ruff format

typecheck:
	source .venv/bin/activate && mypy --strict .

check: lint typecheck test-all

verify: lint typecheck test-all

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
	@rm -f /tmp/agent-step8-committed.txt /tmp/agent-*-done.txt /tmp/agent-step0-complete.txt
	@rm -f /tmp/agent-trace-lead-engineer-*.jsonl 2>/dev/null || true
	@echo "Agent guards primed. Safe to spawn lead-engineer."

# Phase gate arm targets — called at terminal step before report output
# Each writes a sentinel that blocks ALL subsequent tool calls via agent-phase-gate.sh
arm-verify-gate:
	@touch /tmp/agent-verify-story-done.txt
	@echo "Verify-story phase gate armed. Report and stop."

arm-qa-gate:
	@touch /tmp/agent-qa-epic-done.txt
	@echo "QA-epic phase gate armed. Report and stop."

arm-close-epic-gate:
	@touch /tmp/agent-close-epic-done.txt
	@echo "Close-epic phase gate armed. Report and stop."

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

# 4b. Commit implementation (agent stages files first with git add <files>)
# Usage: make commit-impl STORY=QWS-0801 MSG="add signal normalization"
commit-impl:
	@[ -n "$(STORY)" ] || (echo "ERROR: STORY required. Usage: make commit-impl STORY=QWS-0801 MSG='summary'"; exit 1)
	git commit -m "$(if $(MSG),$(MSG),impl($(STORY)): implementation)"

# 4c. Commit verification sweep (agent stages files first with git add <files>)
# Usage: make commit-test STORY=QWS-0801
commit-test:
	@[ -n "$(STORY)" ] || (echo "ERROR: STORY required. Usage: make commit-test STORY=QWS-0801"; exit 1)
	git commit -m "$(if $(MSG),$(MSG),test($(STORY)): verification sweep — fixtures, demo seed, DoD)"

# 4d. Commit post-epic QA fixes + push to release branch (agent stages files first)
# Usage: make commit-push-qa EPIC=6
commit-push-qa:
	@[ -n "$(EPIC)" ] || (echo "ERROR: EPIC required. Usage: make commit-push-qa EPIC=6"; exit 1)
	git commit -m "$(if $(MSG),$(MSG),qa(epic-$(EPIC)): post-epic QA fixes — fixtures/seed)"
	git push origin $(RELEASE_BRANCH)

# 4e. Commit story closure
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

