.PHONY: help test lint check site build example release

# agentope's everyday commands. `make release BUMP=patch|minor|major` cuts a release.

help:  ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

test:  ## Run the Python tests
	uv run pytest -q

lint:  ## Lint and format-check the package, the example and the site
	uv run ruff check src tests examples
	uv run ruff format --check src tests examples
	cd site && npx biome check src && npx tsc --noEmit

site:  ## Build the static site into site/dist/client
	npm --prefix site run build

build:  ## Build the sdist and wheel into dist/ and check them
	rm -rf dist
	uv build
	uvx twine check dist/*

example:  ## Rerun the support-agent example and refresh the site's data
	uv run python examples/support_agent/run.py

check: lint test site build  ## Everything a release runs before it changes anything

# Cut a release: check, bump the version everywhere, commit, tag, push. Pushing the
# tag triggers .github/workflows/release.yml, which tests, builds and publishes to
# PyPI, then creates the GitHub release.
#
# Run it from main with a clean tree, in VS Code's terminal (pushing to this repo
# uses VS Code's GitHub sign-in). The checks run before anything is written, so a
# failing release leaves no trace. bump-my-version only edits files (see
# [tool.bumpversion] in pyproject.toml); uv.lock is refreshed afterwards so the
# tagged commit carries the new version everywhere, and everything lands in one
# commit.
release:  ## Cut a release: make release BUMP=patch|minor|major
	@test -n "$(BUMP)" || { echo "Usage: make release BUMP=patch|minor|major"; exit 1; }
	@case "$(BUMP)" in patch|minor|major) ;; *) echo "BUMP must be patch, minor or major"; exit 1;; esac
	@test "$$(git rev-parse --abbrev-ref HEAD)" = main || { echo "Release from main only (on $$(git rev-parse --abbrev-ref HEAD))."; exit 1; }
	@git diff --quiet && git diff --cached --quiet || { echo "Working tree not clean: commit or stash first."; exit 1; }
	@test -z "$$(git status --porcelain --untracked-files=normal)" || { echo "Untracked files present: commit, ignore or remove them first."; exit 1; }
	uv lock --check
	$(MAKE) check
	uvx bump-my-version bump $(BUMP)
	uv lock
	@v=$$(uvx bump-my-version show current_version); \
	git add -A; \
	git commit -m "Release v$$v"; \
	git tag -a "v$$v" -m "v$$v"; \
	echo "Tagged v$$v."
	git push --follow-tags
