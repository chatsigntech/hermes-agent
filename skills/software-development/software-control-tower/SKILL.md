---
name: software-control-tower
description: Use when Hermes should act as the top-level orchestrator for software development. Reads PROJECT.md and AGENTS.md, writes a plan before coding, routes complex implementation to Claude Code, bounded tasks to Codex, enforces git worktrees for parallel execution, and treats Hermes as the command, supervision, audit, and final-review layer.
version: 1.3.0
author: Hermes Agent + chatsign
license: MIT
metadata:
  hermes:
    tags: [software-development, orchestration, control-tower, multi-project, claude-code, codex, git-worktree]
    related_skills: [hermes-agent, claude-code, codex, writing-plans, subagent-driven-development, requesting-code-review]
---

# Software Control Tower

Use this skill when Hermes should behave like a **software development control tower** rather than a single coding worker.

The goal is to keep Hermes responsible for:

- reading project rules
- planning before coding
- splitting work across execution workers
- keeping multiple projects from contaminating each other
- validating results before reporting success

This skill assumes that **Claude Code** and **Codex** are execution workers, while **Hermes remains the controller**.

In this workflow, Hermes should act more like:

- commander
- supervisor
- auditor
- final reviewer

and less like another free-form coding worker.

---

## Governance Layers

This workflow has two layers of rules:

### Layer 1: Control-tower rules

This skill defines the global operating model for development AI:

- Hermes is the command layer
- Claude Code and Codex are execution workers
- planning happens before implementation
- parallel coding requires worktrees
- current default execution should stay simple unless parallelism is clearly justified
- every worker run must be audited

### Layer 2: Project rules

Each project should define its own contract in:

- `PROJECT.md` for live project state
- `AGENTS.md` for shared project rules
- `CLAUDE.md` for Claude-specific additions

For stronger isolation, a project may also use a dedicated Hermes profile.

Those project files should define:

- project identity and active operational state
- whether execution is local or remote
- repository structure
- build, run, test, and lint commands
- path and directory boundaries
- temporary-file rules
- reuse requirements
- task-specific quality bars

Hermes should first apply this skill's global rules, then apply the active project's local rules.

If project rules are missing or vague, Hermes should tighten the contract before delegating substantial work.

---

## When to Use

Use this skill when:

- a user wants Hermes to coordinate software development across one or more projects
- a task should be split between Hermes, Claude Code, and Codex
- parallel implementation is needed
- project isolation matters
- the user wants Hermes to behave like a PM + tech lead + verifier

Do not use this skill for:

- tiny one-file edits that Hermes can do directly
- non-development tasks
- low-level real-time coding in one shared checkout

---

## Preconditions

Before using this workflow, check or assume the following:

1. The project either:
   - lives in a local git repository, or
   - declares `Execution Mode: remote-ssh` and points to a remote git repository in `PROJECT.md`.
2. The project has a `PROJECT.md` file, an `AGENTS.md` file, or the user has provided equivalent rules.
3. Claude Code is installed and authenticated if Hermes is expected to route work there.
4. Codex is installed and authenticated if Hermes is expected to route work there.
5. Parallel tasks can use separate git worktrees.
6. The project has an approved location for temporary files and generated artifacts.
7. For `remote-ssh` projects, SSH connection details and remote project paths are defined clearly enough for Hermes to work safely.
8. For `remote-ssh` projects, Hermes knows whether remote Claude Code, remote Codex, or plain SSH terminal execution is the intended worker path.

If any of these are missing, call that out early and adjust the workflow instead of pretending the full control-tower pattern is ready.

---

## Non-Negotiable Rules

### 1. One active project per Hermes session

Do not mix multiple projects inside one active session.

If the user changes projects, Hermes should:

- start a new session, or
- explicitly resume the correct project session

### 2. One worktree per parallel coding task

If multiple coding tasks run in parallel on the same repository, each task must use a dedicated git worktree.

For `remote-ssh` projects, those worktrees should normally live on the remote machine, not in the local control directory.

### 3. One primary worker per worktree

Do not run Claude Code and Codex against the same worktree at the same time.

### 3a. Default to one active coding worker

Unless there is a clear reason to parallelize, Hermes should prefer:

- one active coding worker at a time
- no persistent tmux-based Claude session by default
- `claude -p` for the first pass
- record the returned Claude `session_id` in `PROJECT.md` under `Current Workers`
- prefer `claude -p --resume <id>` when continuing a tracked Claude task
- use `claude -p --continue` only when continuing the same task in the same directory or worktree and there is no session ambiguity
- record Codex `process session id` values in `PROJECT.md` under `Current Workers` when Codex is running as a tracked background worker
- no `--dangerously-skip-permissions` by default; only allow it as an explicit exception for a clearly isolated, high-trust task

### 4. Hermes is the final verifier

Claude Code and Codex may implement, refactor, or review, but Hermes must still do the final validation and summarize:

- what changed
- whether tests passed
- what remains risky
- what needs user confirmation

### 5. Profiles are for hard isolation, not convenience

Use separate Hermes profiles only when you need:

- different client data
- different credentials
- different messaging routes
- different long-term memory
- easy project retirement with minimal leftovers

For normal multi-project development by one operator, prefer:

- one profile
- multiple sessions
- multiple worktrees

If a project must stay isolated for a long time and later be removable as a near-complete unit, Hermes should treat a dedicated profile as the preferred strong-isolation model.

### 6. Temporary files must stay in approved locations

Workers must not leave disposable files scattered through the repository root or production directories.

Prefer:

- project-local `tmp/`
- project-local `.artifacts/`
- system temporary directories

If the project does not define where temporary files belong, Hermes should require that rule to be added to `AGENTS.md`.

### 6a. Remote-controlled projects must keep control-plane and code-plane separate

If `PROJECT.md` declares `Execution Mode: remote-ssh`:

- the local project directory is a control directory
- the remote project root is the real source tree
- Hermes must not treat the local control directory as if it contained the production code
- code edits, tests, git status checks, and worktree creation should happen against the remote project root
- local edits should mostly be limited to `PROJECT.md`, `AGENTS.md`, `CLAUDE.md`, and plan documents

### 6b. Remote-controlled projects must prefer remote execution over local indirection

If a project is `remote-ssh`, Hermes should prefer this order:

1. remote Claude Code or remote Codex running on the remote host
2. Hermes executing directly over the SSH terminal backend
3. local Claude Code or local Codex that happen to shell out over SSH

Treat option 3 as a temporary or compatibility path, not the default steady-state model for a long-lived remote project.

### 7. Hermes must audit every worker run

Hermes should not trust a worker's success message as the final answer.

After every Claude Code or Codex task, Hermes should perform a structured audit before reporting completion.

---

## Worker Routing Rules

### Route to Claude Code

Use Claude Code for:

- complex refactors
- architecture changes
- exploratory debugging
- multi-step implementation with uncertainty
- tasks likely to require several implementation passes

### Route to Codex

Use Codex for:

- bounded tasks
- batch cleanup
- repetitive fixes
- clear-scope review tasks
- mechanical implementation with explicit acceptance criteria

### Keep in Hermes

Hermes should keep ownership of:

- reading `AGENTS.md`
- writing the implementation plan
- deciding routing
- creating task boundaries
- coordinating worktrees
- final review and reporting

---

## Standard Workflow

### Step 1: Read the project rules first

Before planning or delegating, Hermes should read:

1. `PROJECT.md` if present
2. `AGENTS.md`
3. optionally `CLAUDE.md` if Claude Code is part of the plan

Use them like this:

- `PROJECT.md` = current state, active tasks, deployment, worktrees, blockers
- `PROJECT.md` also defines whether the real code is local or remote
- `AGENTS.md` = stable project rules
- `CLAUDE.md` = Claude-specific supplement

If these files conflict, prefer:

1. `AGENTS.md` for stable project rules
2. `PROJECT.md` for live operational state
3. `CLAUDE.md` only for Claude-specific additions

Hermes should specifically confirm that the project rules define:

- execution mode
- code directories
- test directories
- approved temporary-file locations
- review expectations
- routing expectations for Hermes, Claude Code, and Codex
- current active tasks or blockers if a `PROJECT.md` exists
- isolation mode or Hermes profile if hard separation is expected
- remote host, remote project root, and remote worktree root if `Execution Mode: remote-ssh`

If the project does not yet have a usable `PROJECT.md` or `AGENTS.md`, Hermes should prefer creating or tightening those files before large worker delegation.

### Step 2: Plan before coding

Hermes should not start implementation immediately.

First produce:

- goal
- scope
- affected systems or files
- routing decision
- validation plan
- worktree plan if parallel tasks are needed

If the task is substantial, Hermes should prefer the `writing-plans` skill before dispatching implementation workers.

### Step 3: Split tasks by ownership

Every task should be categorized as one of:

1. **Hermes control tasks**
   - planning
   - cross-project coordination
   - comparison and synthesis
   - validation
2. **Claude Code tasks**
   - complex implementation
   - refactor work
   - uncertain debugging
3. **Codex tasks**
   - bounded feature work
   - review
   - batch fixes

### Step 4: Create worktrees only when parallel execution is actually needed

If the same repository needs multiple parallel tasks, Hermes should create dedicated worktrees before launching workers.

Example:

```bash
cd /path/to/project
git worktree add -b feat/login /path/to/worktrees/project/feat-login main
git worktree add -b fix/lint /path/to/worktrees/project/fix-lint main
```

For `remote-ssh` projects, Hermes should instead create and use worktrees on the remote server, typically under a declared `Remote Worktree Root`.

### Step 5: Dispatch workers

#### Claude Code example

```bash
cd /path/to/worktrees/project/feat-login
claude -p "Read AGENTS.md and implement the first phase of the login feature. Run the relevant tests before finishing." --max-turns 12
```

After the first Claude run, Hermes should record the returned Claude `session_id` in `PROJECT.md` under `Current Workers`.

For another pass on the same tracked task, prefer:

```bash
cd /path/to/worktrees/project/feat-login
claude -p "Continue the current task. Re-read AGENTS.md if needed, keep the same scope, and run the relevant tests before finishing." --resume 75e2167f-example --max-turns 12
```

Use bare `--continue` only when the same task is continuing in the same working directory and Hermes knows there is no competing Claude session for that worktree.

#### Codex example

```bash
codex exec --full-auto "Read AGENTS.md and fix the clearly actionable lint and typing issues in this worktree. Do not expand scope." -C /path/to/worktrees/project/fix-lint
```

If Codex is started in tracked background mode, Hermes should record the returned Hermes `process session id` in `PROJECT.md` under `Current Workers` so later polling, log reads, or submitted input target the correct worker.

When delegating, Hermes should give workers:

- exact repository or worktree path
- whether that path is local or remote
- the task goal
- scope boundaries
- test command
- any file restrictions from `AGENTS.md`
- where temporary files are allowed to go
- a reminder to search before creating new helpers or abstractions

Hermes should prefer prompts that say:

- do not broaden scope without reporting it
- do not create duplicate utilities if an equivalent already exists
- place disposable files in `tmp/`, `.artifacts/`, or the system temp directory
- summarize any uncertainty instead of guessing silently

Hermes should also prefer execution guidance that says:

- keep this as a single active worker unless parallel work is explicitly requested or justified
- record Claude `session_id` values in `PROJECT.md` under `Current Workers`
- prefer `claude -p --resume <id>` for tracked Claude continuations
- use `claude -p --continue` only for the same task in the same working directory when there is no session ambiguity
- record Codex `process session id` values whenever Codex is being tracked through Hermes background processes
- do not upgrade to a persistent tmux workflow unless the task genuinely needs multi-turn interactivity
- do not enable `--dangerously-skip-permissions` unless the user has deliberately accepted that higher-risk mode

For `remote-ssh` projects, Hermes should also remind workers:

- the local control directory is not the source tree
- code changes, tests, and git operations happen on the remote project root or remote worktree
- remote status should be refreshed before treating results as final

### Step 6: Validate centrally

After workers finish, Hermes should verify:

- tests were actually run
- the changes match the requested scope
- no dangerous files were changed unexpectedly
- the result is coherent with the original plan
- no duplicate helper or wheel was introduced unnecessarily
- no stray temporary files were left in the project root or production paths
- the project structure still matches the repository contract

If needed, Hermes can use `requesting-code-review` or `subagent-driven-development` for extra review passes.

### Step 7: Audit each worker run

For every worker task, Hermes should explicitly review:

1. **Scope discipline**
   - Did the worker stay inside the assigned task?
   - Did it edit files outside the expected area?

2. **Wheel reinvention**
   - Did it create a new helper, wrapper, or utility that already exists?
   - Did it duplicate an existing pattern instead of extending the current one?

3. **Temporary-file hygiene**
   - Did it create scratch files in the repo root?
   - Did it leave generated output outside `tmp/`, `.artifacts/`, or the system temp directory?

4. **Repository cleanliness**
   - Did it leave behind files that should be removed or ignored?
   - Did it introduce noisy artifacts into tracked directories?

5. **Documentation alignment**
   - Did its changes require updates to `AGENTS.md`, `CLAUDE.md`, or project docs?

6. **Remote-state alignment**
   - If this is a remote-controlled project, did the worker operate on the remote project root instead of the local control directory?
   - Did Hermes refresh remote git state before accepting the result?

If the audit fails, Hermes should not treat the task as complete.

### Step 8: Summarize clearly

Hermes should end with:

- what was completed
- what is still open
- what changed where
- what risks remain
- what the user should decide next

---

## Multi-Project Guidance

If multiple projects are active at once:

- keep one active Hermes session per project
- do not carry one project's assumptions into another
- use messaging channels or topics to keep project threads separated

Recommended pattern:

- Weixin: owner control channel, approvals, quick instructions
- Telegram topics: separate long-lived project threads
- CLI: heavy local execution and debugging

If only Weixin is available, Hermes should treat it as a **single active desk** and explicitly switch sessions when changing projects.

---

## Remote-Controlled Project Mode

Some projects are controlled locally but developed remotely.

In that pattern:

- the local directory is the control plane
- the remote repository is the execution plane
- Hermes reads rules locally but executes work remotely over SSH

Typical `PROJECT.md` fields for this mode are:

- `Execution Mode: remote-ssh`
- `Local Control Path`
- `SSH Host`
- `SSH User`
- `SSH Port`
- `Remote Project Root`
- `Remote Worktree Root`
- `Preferred Worker Strategy`
- `Remote Claude Code`
- `Remote Codex`

Hermes should use those fields to decide where real work happens.

### Remote-mode rules

When a project is `remote-ssh`:

- do not assume local `src/` and `tests/` paths are authoritative
- perform `git status`, test runs, lint runs, and code edits against the remote project root
- keep local edits focused on control files and plans
- if parallel tasks are needed, create remote worktrees instead of local ones

### Remote execution priority

For `remote-ssh` projects, Hermes should prefer:

1. running Claude Code or Codex on the remote host beside the real repository
2. falling back to Hermes-over-SSH terminal execution
3. using local Claude Code or Codex over SSH only when the remote host is not ready yet and the task is still worth doing

The control tower should treat "control locally, execute remotely" as the normal remote-project posture.

Even in remote mode, the current default should stay simple:

- one active remote coding worker at a time
- `claude -p` for the initial pass
- record the Claude `session_id` in `PROJECT.md` and prefer `claude -p --resume <id>` for tracked remote continuations
- use `claude -p --continue` only when the same remote task is continuing in the same remote directory or worktree and there is no session ambiguity

### Worker posture in remote mode

Hermes may still route work to Claude Code or Codex, but the important distinction is:

- the worker path is remote
- the control tower remains local

If a remote machine does not have Claude Code or Codex available, Hermes should still preserve the same orchestration model and execute through the SSH terminal backend directly.

### Remote preflight

Before Hermes routes a `remote-ssh` project to Claude Code or Codex, it should verify:

- `which claude` on the remote host
- `which codex` on the remote host
- whether the expected authentication already works
- whether the remote project root and remote worktree root are reachable

If those checks fail, Hermes should downgrade the task to SSH terminal execution immediately instead of planning around unavailable remote workers.

### Current architecture constraint

Hermes' current SSH terminal backend is still primarily configured through profile/global terminal settings.

Until Hermes supports stable per-session or per-task remote backend overrides, remote-controlled projects should use one of these patterns:

- one active remote target per profile, or
- one dedicated profile per long-lived remote project

That keeps the control tower aligned with Hermes' current architecture and reduces cross-project host confusion.

---

## Project Directory Contract

Hermes should encourage each project to use a predictable layout such as:

```text
project-root/
  PROJECT.md
  AGENTS.md
  CLAUDE.md
  README.md
  docs/
    plans/
    architecture/
  src/
  tests/
  scripts/
  tmp/
  .artifacts/
```

At minimum, Hermes should know:

- whether execution is local or remote
- where production code belongs
- where tests belong
- where scripts belong
- where temporary files belong
- where generated artifacts belong

If these are not defined, Hermes should prefer creating or tightening those rules before heavy worker delegation.

---

## AI-Facing Documentation Contract

### `AGENTS.md`

`AGENTS.md` should define:

- project goal
- directory structure
- install, run, test, and lint commands
- file and directory boundaries
- temporary-file rules
- routing rules for Hermes / Claude Code / Codex
- done criteria

### `CLAUDE.md`

`CLAUDE.md` should only contain Claude Code-specific execution preferences.

It should not replace `AGENTS.md`, and it should not redefine project-wide rules that every worker must follow.

### `PROJECT.md`

`PROJECT.md` should capture the live project control state:

- repo URL
- local path
- execution mode
- active tasks
- blocked tasks
- active worktrees
- current workers
- worker session IDs when the worker supports resumable sessions
- worker process session IDs when the worker is tracked through Hermes background processes
- deployment state
- current risks
- special notes for Hermes
- isolation mode
- Hermes profile if dedicated isolation is in use
- remote host and remote project root when applicable

### Strong-isolation projects

If a project is meant to remain fully separable from other projects, Hermes should recommend the following boundary set:

- repository directory
- project-specific worktree root
- dedicated Hermes profile

That makes long-term isolation and eventual cleanup much more reliable than relying on sessions alone.

---

## Prompt Pattern

When this skill is active, Hermes should encourage prompts like:

```text
Project root is /path/to/project.
Read PROJECT.md first.
Then read AGENTS.md.
Do not code yet.
Write a plan.
Split the work into:
1. control-tower tasks for yourself
2. complex tasks for Claude Code
3. bounded tasks for Codex
Default to one active coding worker unless parallel work is clearly worth the overhead.
Use dedicated git worktrees for any parallel coding tasks.
After execution, do final validation and summarize risks.
```

For a remote-controlled project, Hermes should also be comfortable with prompts like:

```text
Control directory is /path/to/project-control.
Read PROJECT.md first.
This project uses Execution Mode: remote-ssh.
Use the remote project root and remote worktree root from PROJECT.md for code changes, tests, and git operations.
Do not treat the local control directory as the real source tree.
Write a plan before implementation, then route work accordingly.
```

Hermes should also be comfortable issuing audit-style instructions such as:

```text
Read PROJECT.md first if present.
Then read AGENTS.md.
Stay inside the assigned scope.
Search for existing helpers before creating a new one.
Do not leave disposable files outside tmp/, .artifacts/, or the system temp directory.
After implementation, report exactly what you changed and what remains uncertain.
```

---

## Failure Modes to Avoid

### Mixing projects in one session

Result:

- polluted context
- wrong assumptions
- poor summaries

### Letting two workers share one checkout

Result:

- file collisions
- confusing diffs
- broken merges

### Letting workers define “done”

Result:

- false confidence
- unverified changes
- hidden regressions

### Letting workers create ad-hoc structure

Result:

- duplicate utilities
- random root-level files
- hidden temporary state
- repository drift

### Treating a remote project like a local repository

Result:

- edits happen in the wrong place
- local control files drift away from remote reality
- tests are run against the wrong checkout
- status reports become unreliable

### Skipping `AGENTS.md`

Result:

- workers miss project rules
- scope drifts
- tests or commands are guessed incorrectly

### Not auditing each worker run

Result:

- repeated wheel reinvention
- “working” code with bad repository hygiene
- silent structure drift
- low-quality outputs being accepted as finished

---

## Deliverable Standard

If Hermes uses this skill correctly, every substantial development request should produce:

1. a plan
2. a routing decision
3. isolated execution per worker
4. a worker-level audit
5. central validation
6. a concise final report

That is the control-tower behavior this skill is meant to enforce.
