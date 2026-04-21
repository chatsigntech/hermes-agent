# Project AI Contract Template

This template is for projects that will be developed under the **Software Control Tower** pattern:

- **Hermes** is the outer control layer
- **Claude Code** and **Codex** are execution workers
- **PROJECT.md** is the live project control file
- **AGENTS.md** is the shared project contract
- **CLAUDE.md** is the Claude Code-specific supplement

This template is intentionally influenced by the common patterns used across modern coding-agent ecosystems:

- `AGENTS.md` as a repo-level instruction file
- `CLAUDE.md` as project memory for Claude Code
- structured project rules instead of repeated prompt instructions
- explicit directory contracts, command contracts, and review gates

Use this file as the canonical starting point when creating a new project or tightening an existing one.

It supports both:

- **local projects** where the repository and code live on the local machine
- **remote-controlled projects** where the local directory is only the control plane and the real code lives on a remote server

---

## Layered Model

The overall rule hierarchy should look like this:

### Layer 1: Global control-tower rules

Defined by the `software-control-tower` skill.

These rules govern:

- planning before coding
- routing to Claude Code vs Codex
- worktree usage
- worker audits
- final verification by Hermes

### Layer 2: Project-level AI contract

Defined inside the project itself.

These files are the main project contract:

- `PROJECT.md`
- `AGENTS.md`
- `CLAUDE.md`

These files govern:

- project identity and operational state
- project structure
- build, run, test, lint commands
- file placement rules
- temporary-file rules
- reuse and architecture rules
- project-specific quality expectations

### Layer 3: Optional profile isolation

This layer is only for projects that need strong separation.

Use a dedicated Hermes profile when you need:

- separate long-term memory
- separate credentials or messaging routes
- stronger client or compliance boundaries
- the ability to remove the project later as a near-complete unit

For ordinary multi-project development by one operator, a shared profile plus good session and worktree discipline is usually enough.

---

## Recommended Repository Structure

Use a predictable structure so both humans and agents know where things belong:

```text
project-root/
  PROJECT.md
  AGENTS.md
  CLAUDE.md
  README.md
  .gitignore
  docs/
    plans/
    architecture/
    decisions/
  src/
  tests/
  scripts/
  tools/
  tmp/
  .artifacts/
```

### Directory meanings

| Path | Meaning |
|------|---------|
| `PROJECT.md` | project control file: repo identity, work queue, deployment, and current state |
| `AGENTS.md` | shared contract for Hermes and all coding workers |
| `CLAUDE.md` | Claude Code-specific supplement |
| `README.md` | human-facing overview |
| `docs/plans/` | implementation plans and execution plans |
| `docs/architecture/` | high-level system structure, module maps, diagrams |
| `docs/decisions/` | architectural decisions and rationale |
| `src/` | production code |
| `tests/` | automated tests |
| `scripts/` | versioned repo scripts |
| `tools/` | internal development tools or utilities that are intentionally part of the repo |
| `tmp/` | disposable project-local temporary files |
| `.artifacts/` | generated reports, review outputs, screenshots, traces, or machine-produced artifacts |

### Structure rules

- Do not create ad-hoc files in the repo root unless the repository explicitly expects them there.
- Do not put disposable files under `src/`, `tests/`, or `docs/`.
- Put scratch output in `tmp/`, `.artifacts/`, or the system temp directory.
- Add `tmp/` and `.artifacts/` to `.gitignore` unless they are intentionally versioned.

### Remote-controlled structure variant

If the real code lives on a remote server, the local directory should be treated as a **control directory**:

```text
project-control/
  PROJECT.md
  AGENTS.md
  CLAUDE.md
  README.md
  docs/
    plans/
    architecture/
```

In this mode:

- the local directory stores project rules and operational state
- the real source tree lives at a remote path such as `/srv/project-a`
- worktrees, tests, and code edits happen remotely
- the local control directory should not pretend to be the real source checkout

---

## Best-Practice `AGENTS.md` Template

Copy and adapt this into the project root as `AGENTS.md`.

````md
# Project AI Contract

## Goal

Describe:
- what this project does
- what the current development priority is
- what success looks like

Example:
- This repository contains the backend and admin UI for the internal ticket workflow system.
- Current priority: stabilize the notification pipeline and improve admin auditability.

## Repository Structure

- Production code: `src/`
- Tests: `tests/`
- Versioned scripts: `scripts/`
- Internal dev tooling: `tools/`
- Plans: `docs/plans/`
- Architecture docs: `docs/architecture/`
- Temporary files: `tmp/`
- Generated review artifacts: `.artifacts/`

Do not create new root-level files unless explicitly required.

## Commands

- Install: `uv sync`
- Run app: `uv run python app.py`
- Run tests: `pytest -q`
- Run targeted tests: `pytest tests/path/to/test_file.py -q`
- Lint: `ruff check .`
- Format: `ruff format .`

If frontend exists, list the frontend commands too.

## Remote-Controlled Project Override

If `PROJECT.md` declares `Execution Mode: remote-ssh`, reinterpret this file with the following rules:

- the local directory is a control directory, not the real source checkout
- `src/`, `tests/`, `scripts/`, and similar paths refer to the remote project root unless explicitly marked local
- install, run, test, lint, and build commands should execute against the remote project root or remote worktree
- the local control directory should usually only hold `PROJECT.md`, `AGENTS.md`, `CLAUDE.md`, plans, and architecture notes

For remote-controlled projects, make the remote nature explicit inside `AGENTS.md` itself. A small clause like this is usually enough:

```md
## Execution Mode

- This project is `remote-ssh`
- The local repository directory is only the control plane
- All code changes, tests, git operations, and worktrees must run against the remote project root declared in `PROJECT.md`
```

## Architecture Boundaries

- Keep business logic in `src/services/`
- Keep API handlers thin
- Keep schema definitions in `src/schemas/`
- Prefer extending existing modules over inventing parallel structures
- Do not introduce a second abstraction for an existing concern unless there is a documented reason

## Reuse Before Create

Before creating:
- a helper
- a utility module
- a wrapper
- a shared abstraction

you must search the codebase for an existing equivalent.

Do not create small one-off helpers that are only used once unless there is a clear readability or reuse benefit.

Do not re-implement an existing pattern under a new name without explaining why.

## Temporary Files and Generated Output

- Put disposable files in `tmp/`, `.artifacts/`, or the system temp directory.
- Do not leave scratch files in the repository root.
- Do not place generated reports next to production code.
- Clean up temporary outputs when they are no longer needed.

## Safety Rules

- Do not commit `.env`, secrets, credentials, or tokens.
- Do not modify production deployment files without explicit approval.
- Do not rewrite old migrations unless the task explicitly requires it.
- Do not widen task scope silently.

## Worker Routing

- Hermes:
  - planning
  - coordination
  - final review
  - final summary
- Claude Code:
  - complex refactors
  - exploratory implementation
  - uncertain debugging
- Codex:
  - bounded changes
  - repetitive cleanup
  - review and verification tasks

Parallel work on the same repository must use separate git worktrees.

## Review Gates

Before declaring a task complete, verify:

- relevant tests passed
- scope stayed within the assignment
- no duplicate helper or wheel was introduced
- no stray temp files remain in the repo root
- docs were updated if behavior changed

## Commit and PR Expectations

- Use concise, imperative commit messages
- Keep commits scoped
- Summarize the purpose of the change
- Mention risks or follow-up work if needed

## Done Criteria

A task is only done when:

- code is implemented
- relevant tests pass
- repository structure remains clean
- temporary files are in approved locations
- the change is explained clearly enough for Hermes to audit
````

---

## Best-Practice `PROJECT.md` Template

Copy and adapt this into the project root as `PROJECT.md`.

This file is intentionally different from `AGENTS.md`:

- `AGENTS.md` is mostly stable policy
- `PROJECT.md` is the live project control surface

````md
# Project Control File

## Identity

- Name: my-project
- Repo: https://github.com/owner/my-project
- Local Path: /Users/chatsign/Projects/my-project
- Local Control Path: /Users/chatsign/Projects/my-project
- Default Branch: main
- Isolation Mode: shared-profile
- Hermes Profile: default
- Stack: Python, FastAPI, React, PostgreSQL
- Type: web service
- Execution Mode: local

## Structure

- Source Dir: `src/`
- Test Dir: `tests/`
- Docs Dir: `docs/`
- Script Dir: `scripts/`
- Temp Dir: `tmp/`
- Artifacts Dir: `.artifacts/`

## Commands

- Install: `uv sync`
- Run Backend: `uv run python app.py`
- Run Frontend: `pnpm dev`
- Test Backend: `pytest -q`
- Test Frontend: `pnpm test`
- Lint: `ruff check . && pnpm lint`
- Build: `pnpm build`

## Remote Execution

- SSH Host:
- SSH User:
- SSH Port: 22
- Remote Project Root:
- Remote Worktree Root:
- Preferred Worker Strategy: `remote-cli` / `ssh-terminal` / `local-cli-over-ssh`
- Remote Claude Code: installed? authenticated?
- Remote Codex: installed? authenticated?
- Remote Python:
- Remote Node:

Fill this section only when `Execution Mode` is `remote-ssh`.

For long-lived remote projects, also record whether this project is expected to:

- share a profile with other remote targets, or
- use a dedicated Hermes profile for host isolation

## Work Queue

### Active
- Stabilize auth refresh-token flow
- Improve admin audit log filtering

### Next
- Add deployment health dashboard
- Review duplicate notification helpers

### Blocked
- Production mail provider credentials pending

### Backlog
- Multi-tenant settings cleanup
- Admin role redesign

## Execution State

### Current Worktrees
- `feat/auth-refresh` -> `/Users/chatsign/Worktrees/my-project/feat-auth-refresh`
- `review/admin-audit` -> `/Users/chatsign/Worktrees/my-project/review-admin-audit`

### Current Workers
- Claude Code: auth refresh implementation
  - Worktree: `feat/auth-refresh`
  - Session ID: `75e2167f-example`
- Codex: audit helper cleanup review
  - Worktree: `review/admin-audit`
  - Process Session ID: `proc_abc123`

### Open Reviews
- PR #142 waiting on test evidence

## Deployment

### Dev
- URL: https://dev.example.com
- Status: healthy

### Staging
- URL: https://staging.example.com
- Status: deployed 2026-04-20

### Production
- URL: https://app.example.com
- Status: healthy
- Last Deploy: 2026-04-18 14:10 UTC
- Rollback: previous release

## Risks

- Notification logic has overlapping helper paths
- Some deployment knowledge still lives only in shell history

## Notes for Hermes

- Treat auth and notification changes as high-risk
- Search for existing helpers before introducing new abstractions
- Temporary files must stay in `tmp/` or `.artifacts/`
- Ask before changing deployment configuration
- Default to one active coding worker at a time unless parallelism is clearly justified
- Prefer `claude -p` for a fresh task
- Record the returned Claude `session_id` under `Current Workers`
- Prefer `claude -p --resume <id>` when continuing a tracked Claude task
- Use `claude -p --continue` only when the same task is continuing in the same directory or worktree and there is no session ambiguity
- Record Codex `process session id` values under `Current Workers` when Codex is running in background mode
- If `Execution Mode` is `remote-ssh`, prefer remote Claude/Codex first, SSH terminal second, and local CLI over SSH only as a temporary fallback
````

### What belongs in `PROJECT.md`

Use `PROJECT.md` for live control-plane information:

- GitHub repo URL
- local path
- execution mode
- current tasks
- active worktrees
- worker assignments
- worker session IDs when the worker supports resumable sessions
- worker process session IDs when the worker is tracked through Hermes background processes
- deployment state
- current risks
- active blockers
- isolation mode
- Hermes profile if the project uses a dedicated one
- remote host and remote project root when applicable

### What does **not** belong in `PROJECT.md`

Do not use it for stable rules that rarely change. Put those in `AGENTS.md` instead.

---

## Isolation and Removal Guidance

### Shared-profile mode

Use:

- one shared Hermes profile
- one project directory
- one project-specific worktree root
- one `PROJECT.md`

This is the default for many internal projects.

### Dedicated-profile mode

Use:

- one dedicated Hermes profile
- one project directory
- one project-specific worktree root
- one `PROJECT.md`

Choose this when the project needs stronger separation or easy retirement.

### Clean removal target

If a project uses dedicated-profile mode, the main cleanup unit becomes:

```text
/Users/chatsign/Projects/my-project
/Users/chatsign/Worktrees/my-project/*
~/.hermes/profiles/my-project/
```

That gives the control tower a clear boundary for long-term operation and eventual deletion.

---

## Best-Practice `CLAUDE.md` Template

Copy and adapt this into the project root as `CLAUDE.md`.

This file should stay smaller than `AGENTS.md`.

````md
# Claude Code Project Notes

## Read Order

1. Read `PROJECT.md` first if it exists
2. Then read `AGENTS.md`
3. Use this file only as a supplement

If this file conflicts with `AGENTS.md`, follow `AGENTS.md` and report the conflict.
If `PROJECT.md` defines execution mode, remote roots, or active worktree state, do not ignore it.

## Claude Workflow

- Prefer scoped changes
- Prefer small commits
- Report uncertainty instead of guessing silently
- Do not broaden task scope without saying so

## Search Before Build

Before adding:
- a helper
- a utility
- a wrapper
- a new internal abstraction

search for an existing equivalent and extend it if appropriate.

## Path Rules

- Scratch files go in `tmp/`, `.artifacts/`, or the system temp directory
- Do not leave disposable files in the repo root
- Do not place generated output in `src/` or `tests/`

## Refactor Rules

- Prefer extending existing modules over creating parallel structures
- If adding a new abstraction, explain why the old one is insufficient
- If introducing a new helper, make sure it is truly reusable

## Handoff Expectation

Before finishing, report:
- files changed
- tests run
- known risks
- follow-up work
````

---

## Hermes Audit Checklist

After each Claude Code or Codex task, Hermes should review against this checklist.

### Scope

- Did the worker stay inside the assigned task?
- Did it touch only the expected files and areas?

### Reuse

- Did it search for existing helpers first?
- Did it introduce duplicate wrappers or utilities?
- Did it create a new abstraction that does not justify its existence?

### Structure

- Did it preserve the repository structure?
- Did it put files in the correct directories?

### Temporary files

- Did it leave stray files in the root?
- Did it place disposable output in `tmp/`, `.artifacts/`, or system temp?

### Validation

- Did it actually run the relevant tests?
- Is there evidence, not just a claim?

### Remote execution

- If the project uses `remote-ssh`, did Hermes refresh remote git state first?
- Did the worker operate on the remote project root or remote worktree instead of the local control directory?
- Are remote worktree paths and active workers still correctly reflected in `PROJECT.md`?

### Documentation

- Did behavior changes require doc updates?
- Does `AGENTS.md` or `CLAUDE.md` need tightening based on what went wrong?

### Project control state

- Does `PROJECT.md` need to be updated to reflect:
  - new active tasks
  - new worktrees
  - changed deployment status
  - newly discovered risks or blockers

---

## How to Use This Template

For a new project:

1. Create the recommended directory structure
2. Add `PROJECT.md` from the template above
3. Add `AGENTS.md` from the template above
4. Add `CLAUDE.md` from the template above
5. Fill in the real commands and architecture boundaries
6. Make the control-tower workflow enforce these rules during every worker run

For an existing project:

1. Map the current structure to the contract
2. Add missing path rules
3. Add missing temporary-file rules
4. Add missing reuse rules
5. Tighten the commands and review gates until Hermes can audit reliably

This is what turns a project from “AI can edit code here” into “AI can develop here under supervision.”
