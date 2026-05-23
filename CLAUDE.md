# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read this first

`AGENTS.md` is the canonical development guide for this codebase (architecture, agent loop, tool registry, profile system, slash-command registry, skin engine, known pitfalls). Read it before any non-trivial change. `CONTRIBUTING.md` covers the skill-vs-tool decision and the skill authoring format. This file only adds what those two don't say.

## Fork context

This is the `chatsigntech/hermes-agent` fork, not the upstream `nousresearch/hermes-agent`.

- `origin` → `chatsigntech/hermes-agent` (push here)
- `upstream` → `nousresearch/hermes-agent` (push is **DISABLED_DO_NOT_PUSH** — never force-push, never `git push upstream`)
- Fork-maintenance strategy lives in `docs/plans/upstream-sync-strategy.md`. The goal is "本地 fork 只保留个人 skill / 文档 / 私有配置；所有 fix / feat 走 upstream PR". When writing code, prefer changes that are upstream-PR-friendly (small, scoped, tested, no fork-only assumptions) over changes that deepen divergence.
- Related design docs: `docs/plans/secret-vault-design.md` (hermes-vault v5.2), `docs/plans/upstream-issue-b4-email-replies.md`.

## Environment & commands

```bash
source venv/bin/activate         # ALWAYS activate before running Python / pytest / hermes

# Tests — pyproject.toml already sets `-n auto` and excludes integration tests
python -m pytest tests/ -q                       # Full suite (~3000 tests, ~3 min)
python -m pytest tests/path/to/test_x.py -q      # Single file
python -m pytest tests/test_x.py::test_name -q   # Single test
python -m pytest -m integration tests/ -q        # Opt-in integration tests (need API keys)

# Run the CLI locally without reinstalling
python -m hermes_cli.main           # or: ./hermes (wrapper script)
hermes doctor                       # diagnose env / config
```

Package manager is **uv**, Python **3.11+**. Install with `uv pip install -e ".[all,dev]"`. There is no separate lint step configured — keep style consistent with surrounding files (PEP 8 with practical exceptions, see `CONTRIBUTING.md` §Code Style).

## Architecture pointers (the minimum to be productive)

- **Tool registry** is the central dispatch surface: `tools/registry.py`. Every tool file calls `registry.register()` at import time; `model_tools.py::_discover_tools()` triggers the imports. Adding a tool touches 3 files (see `AGENTS.md` §Adding New Tools).
- **Slash commands** are defined once in `hermes_cli/commands.py::COMMAND_REGISTRY` (`CommandDef`). Everything downstream (CLI dispatch, Gateway dispatch, Telegram menu, Slack mapping, autocomplete, help) is derived from that single list. Don't add a command in only one of those surfaces.
- **Agent loop** lives in `run_agent.py::AIAgent.run_conversation()` — synchronous OpenAI-format messages, tool dispatch in-loop, context compression at the boundary. Do not insert mutations of past messages, toolsets, or system prompt mid-conversation — that breaks prompt caching (see `AGENTS.md` §Prompt Caching Must Not Break).
- **Profiles** isolate `HERMES_HOME`. Use `get_hermes_home()` / `display_hermes_home()` from `hermes_constants` — **never** hardcode `~/.hermes` or `Path.home() / ".hermes"`. This rule applies to tests too (see the `_isolate_hermes_home` fixture in `tests/conftest.py`).
- **Two CLI entry points**: `hermes` (interactive TUI, `hermes_cli/main.py`) and the messaging `gateway/run.py` (Telegram/Discord/Slack/WhatsApp/Signal/Email). Many slash commands work in both; check `cli_only` / `gateway_only` flags on the `CommandDef`.

## Project conventions

- **Temp / scratch files** go in `./temp/` (gitignored). Do not scatter `*.log`, `*.json` dumps, or one-off debug scripts in the repo root.
- **Test placement**: project-wide tests live in `tests/` mirroring source layout (`tests/gateway/`, `tests/hermes_cli/`, etc.). The user's global rule about `test/` subdirectories applies to *new* small modules, not to this established layout — extend `tests/` when adding tests for existing modules.
- **Commits**: do not run `git commit` unless the user explicitly asks. Even when they do, keep one semantic change per commit; if the diff mixes refactor + feature + docs, split it. Commit message style: conventional-commits prefix (`fix(email):`, `docs(plans):`, `feat(skills):`) — check `git log --oneline -20` for the local convention.
- **Plans / design docs**: `docs/plans/*.md` (mostly Chinese, design + rationale), `plans/*.md` (upstream-style feature plans), `.plans/*.md` (in-progress local). The fork-sync strategy doc is the source of truth for which local commits go upstream vs. stay local.
- **Generated / large files** to leave alone unless asked: `cli.py` (~446 KB — the TUI orchestrator is genuinely that large), `run_agent.py` (~549 KB), `uv.lock`, `package-lock.json`. They are real source, not artifacts — edit surgically with `Edit`, never rewrite with `Write`.

## Known pitfalls (in addition to AGENTS.md §Known Pitfalls)

- `pyproject.toml` `[tool.pytest.ini_options]` sets `addopts = "-m 'not integration' -n auto"` — that's why bare `pytest` excludes integration tests and parallelizes by default. Do not strip `-n auto` from CI without measuring; it shaves ~3× off the runtime.
- The `matrix` extra is Linux-only in the `all` extra (`python-olm` is broken on modern macOS). Don't add it back unconditionally.
- The `temp/` directory is currently untracked and contains local scratch — do not `git add temp/`.

## When in doubt

- Architecture/extension questions → `AGENTS.md`
- "Should this be a skill or a tool?" → `CONTRIBUTING.md` (almost always **skill**)
- "Will this conflict with upstream?" → `docs/plans/upstream-sync-strategy.md`
