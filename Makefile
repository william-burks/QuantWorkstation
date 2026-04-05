# --- CONFIGURATION ---
# Update this variable once per release cycle
REL_VER = 26.4.0
# ---------------------

RELEASE_BRANCH = release/$(REL_VER)
MASTER_BRANCH = master

# Internal helper to check for uncommitted changes
check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Your working directory is dirty. Commit or stash changes."; \
		exit 1; \
	fi

# 1. Merge current feature branch into Release
# Usage: Stay on feature/yy.m.v/QWS-xxxx and run 'make to-release'
to-release: check-clean
	$(eval FEATURE_BRANCH=$(shell git symbolic-ref --short HEAD))
	@echo "Merging $(FEATURE_BRANCH) into $(RELEASE_BRANCH)..."
	git checkout $(RELEASE_BRANCH)
	git pull origin $(RELEASE_BRANCH)
	git merge $(FEATURE_BRANCH)
	git push origin $(RELEASE_BRANCH)
	@echo "Done! Returning to $(FEATURE_BRANCH)..."
	git checkout $(FEATURE_BRANCH)

# 2. Merge Release into Master
# Usage: run 'make to-master'
to-master: check-clean
	@echo "Merging $(RELEASE_BRANCH) into $(MASTER_BRANCH)..."
	git checkout $(MASTER_BRANCH)
	git pull origin $(MASTER_BRANCH)
	git merge $(RELEASE_BRANCH)
	git push origin $(MASTER_BRANCH)
	@echo "Done! Master is updated."
	git checkout $(RELEASE_BRANCH)

