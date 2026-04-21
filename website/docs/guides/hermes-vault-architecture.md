---
sidebar_position: 15
title: "Hermes Vault Architecture"
description: "Design a profile-aware encrypted secret vault for Hermes without breaking core architecture or upgradeability"
---

# Hermes Vault Architecture

This document proposes an **upgrade-safe secret management architecture** for Hermes Agent.

The goal is to let Hermes work with sensitive values such as:

- server passwords
- SSH passphrases
- deployment tokens
- API keys that should not live in plain text

without turning ordinary chat history into a secret store.

This design is intentionally **additive**. It is meant to fit Hermes as it exists today:

- profile-aware
- config-driven
- messaging-capable
- transcript-persistent
- skill-oriented

while minimizing changes that would be fragile across upstream upgrades.

---

## Compatibility Contract

The vault must follow a strict compatibility contract so it can be added to Hermes without turning every future upstream update into a merge problem.

### Contract rules

1. **Vault is additive, not replacement-first**
   - The vault is a new subsystem.
   - It does not replace `.env`, `config.yaml`, `state.db`, memory, or gateway authorization in phase 1.

2. **Vault does not change transcript storage schema**
   - No new secret-specific columns are added to `state.db` in the first implementation.
   - Existing transcript persistence remains intact.
   - Secret safety is enforced before persistence, not by rewriting the database layer.

3. **Vault integrates only through narrow seams**
   - credential resolution
   - execution-time environment injection
   - CLI vault commands
   - optional gateway lock-status notification

4. **Secret interception happens only at ingress boundaries**
   - CLI user-input ingress
   - gateway message ingress
   - not scattered across memory, transcript, prompt-building, and storage internals

5. **Web unlock is not coupled to the main gateway or dashboard service**
   - The first implementation should use a dedicated local unlock process or local-only unlock mode.
   - Messaging platforms may point the user to unlock, but should not become the unlock transport for passwords.

6. **Resolver behavior must be explicit**
   - Secrets are only loaded from the vault when a caller explicitly asks for a vault-backed alias or key.
   - Existing `.env`-only behavior must remain stable until a later migration phase.

This contract is what makes the design upgrade-safe in practice.

---

## Why Hermes Needs This

Hermes already has strong security features:

- user authorization and pairing
- dangerous command approval
- container isolation
- secret redaction in logs and tool output
- profile-scoped state directories

But Hermes is **not currently a dedicated credential vault**.

Today, if a user pastes a password into an ordinary conversation, that value may:

- enter the active prompt
- be stored in session history
- be written into `state.db`
- be copied into memory if the agent decides it matters

That is the exact gap this design closes.

---

## Design Goals

The vault should provide all of the following:

1. **Encrypted storage** for runtime secrets
2. **Explicit unlock** by the user before secrets become readable
3. **Profile-aware isolation** so each Hermes profile gets its own vault
4. **No secret persistence in ordinary chat history**
5. **No secret leakage to logs, tool output, or UI display**
6. **Minimal impact on existing Hermes architecture**
7. **Low merge conflict risk when Hermes is upgraded upstream**

---

## Non-Goals

This design does **not** try to make Hermes into:

- a general-purpose enterprise KMS
- a replacement for 1Password, Keychain, or Vault
- a remote secret synchronization platform
- a universal bootstrap secret manager

Hermes should remain a local agent platform with a strong local secret boundary.

---

## Core Architectural Principle

The vault must be treated as a **new isolated subsystem**, not as a tweak to the memory system or a special use of `.env`.

That means:

- secrets do **not** belong in `PROJECT.md`
- secrets do **not** belong in `AGENTS.md`
- secrets do **not** belong in `MEMORY.md`
- secrets do **not** belong in normal chat transcripts

Instead:

- project files store **references and aliases**
- the vault stores **sensitive values**
- Hermes resolves secrets only at execution time, after unlock

---

## Recommended Storage Layout

The vault should live under the active `HERMES_HOME`, which keeps it compatible with profiles.

```text
{HERMES_HOME}/
  vault/
    secrets.enc
    metadata.json
    status.json
```

### Why this layout fits Hermes

- It uses `get_hermes_home()` from `hermes_constants.py`, so it is automatically profile-safe.
- It does not overload `.env`, `config.yaml`, `state.db`, or memory files.
- It avoids database migrations unless they are clearly justified later.

### File responsibilities

| File | Purpose |
|------|---------|
| `secrets.enc` | encrypted secret payloads |
| `metadata.json` | non-secret key names, timestamps, hint, version |
| `status.json` | lock state, last unlock time, timeout metadata, no plaintext secrets |

---

## Secret Classes

Hermes should separate secrets into two classes.

### 1. Bootstrap secrets

These are the few secrets required to get Hermes to a usable unlock state.

Examples:

- a token needed to deliver an unlock notification
- a local web unlock binding configuration

These should remain outside the main vault, or be handled by an OS-native secret store later.

### 2. Runtime secrets

These are the values Hermes should keep in the encrypted vault.

Examples:

- `server.prod.password`
- `server.prod.ssh_passphrase`
- `deploy.github.token`
- `db.production.password`

This separation is important. If Hermes needs a secret in order to receive the very first unlock interaction, that secret cannot live behind the same lock.

### What belongs where

| Secret class | Recommended location |
|------|---------|
| bootstrap notification token | OS-native secret store or existing bootstrap config |
| vault master password | user input only, never persisted in config |
| runtime API keys and passwords | Hermes vault |
| public hostnames, IPs, usernames | `PROJECT.md` |

---

## Encryption Model

The `myAgent` implementation is a good reference point:

- password-based key derivation
- encrypted JSON payload
- unlock into memory only

For Hermes, the preferred model is:

- **Argon2id** or **scrypt** for password-based key derivation
- authenticated encryption for secret values
- atomic file writes
- no plaintext caching to disk after unlock

If implementation simplicity is the first priority, a staged approach is acceptable:

1. start with a proven local encrypted-file model
2. keep the subsystem isolated behind a narrow API
3. allow future migration to stronger crypto without changing caller code

The most important rule is not the exact cipher suite. The most important rule is that all callers go through a single vault API.

---

## Unlock Model

### Recommended behavior

Hermes starts in one of two states:

- `unlocked` when no vault exists
- `locked` when a vault exists but has not been unlocked in this process

Unlock should happen through **trusted local channels**, not ordinary conversational text.

### Preferred unlock channels

1. **CLI secure prompt**
2. **Dedicated local web unlock page**
3. **Optional notification channel that points the user to local unlock**

### Important rule

Messaging platforms such as Telegram, Weixin, Email, Slack, or Discord should **not** be used to send the master password itself.

They may:

- notify the user that Hermes is locked
- provide a local unlock link
- show lock status

They should not:

- receive the password as normal message text
- store the password in transcripts
- echo the password back

This is exactly where the `myAgent` design is strong: Telegram carries the unlock link, not the password.

### Recommended first implementation

The first Hermes implementation should prefer:

- `hermes vault unlock` from the local CLI
- optionally `hermes vault unlock --web` or `hermes vault serve-unlock`

It should not require changes to the primary gateway request/response path in phase 1.

---

## First-Interaction Unlock Flow

The desired user experience is:

1. Hermes starts
2. Hermes detects that the vault exists and is locked
3. Hermes allows only a small set of safe actions
4. The first trusted user interaction triggers unlock
5. After successful unlock, runtime secrets become available in memory

### What "first interaction" should mean

For Hermes, this should mean:

- first trusted **local** CLI interaction
- or first trusted **local web unlock** interaction

It should **not** mean:

- first arbitrary message in Telegram
- first arbitrary message in Weixin
- first email reply

Otherwise the password would re-enter the ordinary message path.

---

## Secret Entry Model

This is the most important design choice:

**Secrets must not enter the system through normal chat messages.**

Instead, Hermes should have dedicated entry paths:

- `hermes vault init`
- `hermes vault unlock`
- `hermes vault lock`
- `hermes vault set <key>`
- `hermes vault list`
- `hermes vault rotate-password`
- `hermes vault delete <key>`

Optionally:

- a local web form for entering a secret value

### Why this matters

If a user sends:

```text
The production server password is hunter2
```

in a regular conversation, then even with a vault subsystem present:

- the message already entered the transcript path
- the message may already have been sent to the model provider
- the message may already have been persisted

So the vault is only truly effective if secret capture has its own non-transcript channel.

### Secret submission rule

In phase 1, secret entry should be supported only through:

- CLI secure prompt
- local unlock web form
- future OS-native integrations

It should not be supported through:

- slash commands carrying plaintext values
- Telegram message bodies
- Weixin message bodies
- email replies

This keeps the secret boundary narrow and predictable.

---

## Display and Redaction Model

Redaction must be enforced at four levels:

1. **Logs**
2. **Tool output**
3. **UI rendering**
4. **Conversation persistence**

Hermes already has part of this through `agent/redact.py`, but the vault design should raise the standard:

- secrets never appear in plaintext in status output
- list views show only key names
- detail views show masked values by default
- logs never include plaintext vault values
- any attempted secret-like input in normal chat should be blocked or diverted

### Example display behavior

```text
server.prod.password = ********
deploy.github.token = ghp_12ab...89cd
```

---

## Transcript and Memory Safety Rules

The vault design should add explicit guardrails to prevent accidental persistence.

### Normal chat path

If Hermes detects that a user is attempting to submit a secret through ordinary chat:

- do not write it to memory
- do not persist it to session transcript
- do not reflect it back to the model in plain text
- ask the user to use the vault flow instead

### Where the guard should live

To avoid invasive architecture changes, this guard should exist only at ingress:

- CLI input handling before normal conversation enqueue
- gateway event handling before transcript persistence

It should not be implemented as scattered patches in:

- `state.db` writes
- memory storage internals
- prompt assembly
- model response post-processing

That would create unnecessary upgrade friction.

### Memory system

`MEMORY.md` and `USER.md` must never contain:

- passwords
- API keys
- passphrases
- raw tokens

They may contain:

- secret aliases
- operational notes like "requires vault key `server.prod.password`"

### Project control files

`PROJECT.md` may contain:

- host alias
- IP address
- username
- purpose
- deployment environment
- vault key references

It must not contain:

- plaintext passwords
- raw API keys
- private key material

---

## Integration Points Inside Hermes

To keep the vault upgrade-safe, integrate at narrow seams that Hermes already treats as extension boundaries.

### 1. `hermes_constants.py`

Use `get_hermes_home()` for all vault paths.

This ensures:

- profile safety
- no hardcoded `~/.hermes`
- compatibility with future profile or container layouts

### 2. `hermes_cli/`

The vault should primarily enter Hermes as **new CLI subcommands**, not as a rewrite of existing config flows.

Recommended:

- `hermes vault init`
- `hermes vault unlock`
- `hermes vault lock`
- `hermes vault set`
- `hermes vault list`
- `hermes vault rotate-password`

This is low-risk because Hermes already has a clear CLI subcommand architecture.

### 2a. Resolver seams

Vault-backed secret resolution should be centralized instead of being spread across the codebase.

The first implementation should define a single narrow resolver contract and plug it into only a few existing aggregation points:

- `hermes_cli/auth.py`
- `agent/auxiliary_client.py`
- `tools/code_execution_tool.py`

These are the right places because they already mediate:

- provider credentials
- runtime client setup
- subprocess environment injection

This prevents future work from scattering vault lookups across unrelated modules.

### 3. `gateway/`

The gateway should only gain lightweight status and notification behavior:

- "Hermes is locked"
- "Unlock required"
- optional unlock URL

Do not make the gateway the primary place where raw secrets are entered.

The gateway's first responsibility should only be:

- show lock state
- explain that unlock is required
- optionally provide a local unlock URL or reminder

This keeps gateway changes shallow and resilient to upstream updates.

### 4. `agent/redact.py`

Extend the existing redaction system rather than inventing a second one.

The vault should register additional redaction patterns or a redaction provider so that:

- logs
- tool output
- gateway echoes
- error traces

all benefit from the same masking pipeline.

### 5. Execution tools

Secrets should be injected into runtime only at the tool boundary, for example:

- terminal subprocess env
- code execution env
- provider credential resolution

This keeps secrets out of the broader agent loop and reduces accidental model exposure.

### 6. Existing `.env` behavior

The first vault implementation must not silently change how `.env` currently works.

That means:

- existing `.env`-backed installs continue working unchanged
- vault-backed keys must be explicitly requested
- migration from `.env` to vault is opt-in

This is one of the most important rules for upgrade safety.

---

## Upgrade-Safe Boundaries

This is the most important section for long-term maintainability.

The vault should be designed so that upstream Hermes upgrades are unlikely to break it.

### Good upgrade-safe choices

- Add a new isolated package such as `security/vault/`
- Add new CLI subcommands instead of changing unrelated command behavior
- Reuse `get_hermes_home()` for path handling
- Reuse `agent/redact.py` for redaction
- Keep vault metadata in files, not in `state.db`
- Keep message schema unchanged unless absolutely necessary
- Keep `.env` as the default behavior until explicit migration happens
- Centralize all vault lookups behind one resolver interface

### Risky choices to avoid

- patching the main chat loop in many places
- changing transcript storage format globally
- rewriting how memory works
- hardcoding profile paths
- storing master password in config or `.env`
- making ordinary slash commands carry secret payloads
- silently changing provider auth precedence for existing users
- mixing unlock web routes into the main dashboard or gateway path too early

### Recommended implementation rule

The rest of Hermes should depend on a narrow vault interface such as:

- `is_locked()`
- `unlock(password)`
- `lock()`
- `get_secret(alias)`
- `set_secret(alias, value)`
- `list_secret_keys()`

This keeps the implementation replaceable.

### Precedence contract

To avoid surprising behavior changes, the first implementation should use this precedence model:

1. explicit vault alias request
2. explicit non-vault config/env request
3. existing `.env` / current resolver behavior

In other words:

- vault use is explicit first
- automatic takeover is delayed
- compatibility wins over ambition in phase 1

This is the simplest way to avoid breaking upstream auth and setup flows.

---

## Profiles and Full Cleanup

The vault should be fully profile-aware.

That gives Hermes a strong property:

- each project profile can have its own secret boundary
- deleting a profile can remove the entire project-specific secret store

### Example

```text
~/.hermes/profiles/project-a/vault/secrets.enc
~/.hermes/profiles/project-b/vault/secrets.enc
```

This is a strong fit for Hermes because profiles already represent full instance isolation.

It also helps with your original requirement:

- keep project A from affecting project B
- later remove project A completely

When a project needs strong isolation, the vault should follow the profile.

---

## Migration Strategy

The safest rollout is incremental.

### Phase 1

- add vault subsystem
- support manual initialization
- support manual unlock
- support secret set/list/get
- keep existing `.env` behavior working
- add a narrow resolver interface, but do not force all credentials through it yet
- keep gateway changes limited to lock-status messaging only

### Phase 2

- add migration helpers from `.env` into vault
- add execution-time secret injection
- add UI redaction improvements
- route selected providers and tools through the centralized resolver
- add ingress secret guards in CLI and gateway

### Phase 3

- add normal-chat secret interception
- add local web unlock
- add optional OS-native backend integration
- optionally support alias-driven default vault resolution for selected secret classes

This phased rollout is important because it avoids a dangerous all-at-once rewrite of auth, config, and messaging behavior.

---

## Relationship to `PROJECT.md`

The control-tower workflow should use the vault like this:

### `PROJECT.md` stores

- host alias
- IP
- username
- deployment role
- secret aliases

Example:

```md
## Infrastructure
- Prod SSH Host: `203.0.113.42`
- Prod SSH User: `deploy`
- Prod Password Secret: `server.prod.password`
- GitHub Deploy Token Secret: `deploy.github.token`
```

### `PROJECT.md` does not store

- actual password
- raw token
- private key

This keeps project operational knowledge in the project, while keeping sensitive values in the vault.

---

## Test Strategy

The vault should be covered by tests at three levels.

### Unit tests

- create/unlock/lock behavior
- wrong password behavior
- rotation behavior
- atomic write behavior
- redaction behavior

### Integration tests

- CLI vault commands
- profile-specific vault paths
- secret injection into subprocess env
- lock-state behavior after process restart

### Safety tests

- ordinary chat input containing a password is refused or redirected
- secret values do not land in transcript storage
- secret values do not land in memory files
- logs remain redacted

---

## Recommended First Implementation Scope

To keep this architecture compatible with upstream Hermes upgrades, the first implementation should stay deliberately small.

Build only:

1. `security/vault/` module
2. `hermes vault ...` CLI commands
3. profile-aware encrypted file storage
4. lock/unlock lifecycle
5. redacted display
6. execution-time secret lookup

Delay:

- deep gateway integration
- remote unlock through ordinary chat
- database schema changes
- broad transcript engine rewrites

That gives Hermes a secure core without destabilizing the rest of the platform.

---

## Final Recommendation

Hermes should adopt a **local, profile-aware encrypted vault** with the following rules:

- secrets live in `get_hermes_home()/vault/`
- unlock is explicit
- unlock happens through trusted non-transcript channels
- messaging channels may notify, but should not carry raw passwords
- `PROJECT.md` stores aliases, not values
- redaction is mandatory across logs, output, and UI
- all integration should be additive and modular

This gives Hermes a strong secret boundary while preserving its current architecture and making future upstream upgrades far less likely to break the feature.
