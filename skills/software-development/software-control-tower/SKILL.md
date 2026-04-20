---
name: software-control-tower
description: Use when Hermes should act as the top-level orchestrator for software development. Reads PROJECT.md and AGENTS.md, writes a plan before coding, routes complex implementation to Claude Code, bounded tasks to Codex, enforces git worktrees for parallel execution, and treats Hermes as the command, supervision, audit, and final-review layer.
version: 1.2.0
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
- every worker run must be audited

### Layer 2: Project rules

Each project should define its own contract in:

- `PROJECT.md` for live project state
- `AGENTS.md` for shared project rules
- `CLAUDE.md` for Claude-specific additions

For stronger isolation, a project may also use a dedicated Hermes profile.

Those project files should define:

- project identity and active operational state
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

1. The project lives in a git repository.
2. The project has a `PROJECT.md` file, an `AGENTS.md` file, or the user has provided equivalent rules.
3. Claude Code is installed and authenticated if Hermes is expected to route work there.
4. Codex is installed and authenticated if Hermes is expected to route work there.
5. Parallel tasks can use separate git worktrees.
6. The project has an approved location for temporary files and generated artifacts.

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

### 3. One primary worker per worktree

Do not run Claude Code and Codex against the same worktree at the same time.

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
- `AGENTS.md` = stable project rules
- `CLAUDE.md` = Claude-specific supplement

If these files conflict, prefer:

1. `AGENTS.md` for stable project rules
2. `PROJECT.md` for live operational state
3. `CLAUDE.md` only for Claude-specific additions

Hermes should specifically confirm that the project rules define:

- code directories
- test directories
- approved temporary-file locations
- review expectations
- routing expectations for Hermes, Claude Code, and Codex
- current active tasks or blockers if a `PROJECT.md` exists
- isolation mode or Hermes profile if hard separation is expected

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

### Step 4: Create worktrees for parallel execution

If the same repository needs multiple parallel tasks, Hermes should create dedicated worktrees before launching workers.

Example:

```bash
cd /path/to/project
git worktree add -b feat/login /path/to/worktrees/project/feat-login main
git worktree add -b fix/lint /path/to/worktrees/project/fix-lint main
```

### Step 5: Dispatch workers

#### Claude Code example

```bash
cd /path/to/worktrees/project/feat-login
claude -p "Read AGENTS.md and implement the first phase of the login feature. Run the relevant tests before finishing." --max-turns 12
```

#### Codex example

```bash
codex exec --full-auto "Read AGENTS.md and fix the clearly actionable lint and typing issues in this worktree. Do not expand scope." -C /path/to/worktrees/project/fix-lint
```

When delegating, Hermes should give workers:

- exact repository or worktree path
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
- active tasks
- blocked tasks
- active worktrees
- current workers
- deployment state
- current risks
- special notes for Hermes
- isolation mode
- Hermes profile if dedicated isolation is in use

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
Use dedicated git worktrees for any parallel coding tasks.
After execution, do final validation and summarize risks.
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
