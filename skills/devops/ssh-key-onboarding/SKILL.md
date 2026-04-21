---
name: ssh-key-onboarding
description: Use when Hermes needs to prepare a server or SSH alias for future passwordless login. Covers selecting or generating a dedicated SSH key, safely registering the public key on the remote host, updating ~/.ssh/config (including optional ProxyCommand such as cloudflared), verifying BatchMode login, and handing the host off to software-control-tower or the SSH terminal backend.
version: 1.0.0
author: Hermes Agent + chatsign
license: MIT
metadata:
  hermes:
    tags: [ssh, remote-ssh, onboarding, authorized-keys, cloudflared, devops]
    related_skills: [software-control-tower, github-auth]
---

# SSH Key Onboarding

Use this skill when Hermes must perform the **one-time preparation work** that turns a remote host from:

- password login only
- or flaky first-time manual login

into a host that later skills and workflows can use through **SSH key login**.

This is a bootstrap skill, not a daily operations skill.

The goal is to leave behind:

- a stable SSH alias in `~/.ssh/config`
- a dedicated key pair or an explicitly chosen existing key
- the public key registered on the remote server
- a verified non-interactive login path
- enough metadata in `PROJECT.md` for `software-control-tower` to use the host later

---

## When to Use

Use this skill when:

- a server currently requires manual password login
- a `remote-ssh` project is being set up for the first time
- Hermes, Claude Code, Codex, or the SSH terminal backend should later connect without manual password entry
- a Cloudflare / `ProxyCommand` SSH host needs to be converted into a reusable key-based host alias

Do not use this skill when:

- the host already supports stable key login
- the task is normal day-to-day remote development
- the user only wants to debug a transient SSH outage
- the task would overwrite unrelated SSH configuration without clear user approval

---

## Core Principles

### 1. Prefer a dedicated key per server or project

Avoid reusing a general-purpose personal SSH key unless the user explicitly wants that.

Preferred pattern:

- one key per important host
- or one key per project family

Example filenames:

- `~/.ssh/hermes_prod_app_ed25519`
- `~/.ssh/project_a_remote_ed25519`
- `~/.ssh/hhkej_cloudflare_ed25519`

### 2. Never ask the user to paste a password into normal chat

If a password is needed for the bootstrap step:

- use direct terminal login
- or ask the user to complete the one-time login manually
- or use a secure secret prompt if a local CLI flow explicitly supports it

Do **not** store the password in:

- `MEMORY.md`
- `USER.md`
- `PROJECT.md`
- ordinary chat messages

### 3. Never overwrite `authorized_keys`

Only append the new public key if it is missing.

Do not delete or replace other keys unless the user explicitly asks.

### 4. Back up local SSH config before editing it

Before changing `~/.ssh/config`, create a backup or preserve the original content.

### 5. Verify with non-interactive SSH before declaring success

The bootstrap is not complete until this kind of test succeeds:

```bash
ssh -o BatchMode=yes <alias> 'echo __SSH_KEY_OK__'
```

For hosts that use `ProxyCommand` or Cloudflare Access, a first attempt may occasionally fail. In that case, retry a small number of times and only declare success once a fully non-interactive login path works.

---

## Inputs to Collect

Before acting, Hermes should determine:

- local alias to use in `~/.ssh/config`
- real hostname or IP
- SSH username
- SSH port
- whether a `ProxyCommand` is required
- whether the host is direct SSH or Cloudflare-mediated SSH
- whether a new dedicated key should be created or an existing key reused
- whether the host belongs to a specific project that should be recorded in `PROJECT.md`

If any of these are unclear, Hermes should pause and clarify them before making irreversible SSH changes.

---

## Standard Workflow

### Step 1: Inspect the current local SSH state

Check:

- whether `ssh` is installed
- whether the alias already exists in `~/.ssh/config`
- whether a suitable dedicated key already exists
- whether the current host can be reached manually

Useful checks:

```bash
which ssh
ssh -V
ls -al ~/.ssh
cat ~/.ssh/config
```

If an alias already exists, do not blindly rewrite it. First understand whether it is:

- correct but incomplete
- stale
- pointing to a different server

### Step 2: Choose the key strategy

Preferred default:

- create a new dedicated `ed25519` key

Typical command:

```bash
ssh-keygen -t ed25519 -C "<label>" -f ~/.ssh/<key-name> -N ""
```

Use an empty passphrase only if that matches the user's automation needs and risk tolerance. If the user wants a passphrase, record that decision operationally but do not store the passphrase in project memory.

### Step 3: Add or update the SSH alias

Preferred alias structure:

```sshconfig
Host <alias>
  HostName <hostname-or-ip>
  User <user>
  Port <port>
  IdentityFile ~/.ssh/<key-name>
  IdentitiesOnly yes
  ServerAliveInterval 30
  ServerAliveCountMax 3
```

If the host requires Cloudflare:

```sshconfig
Host <alias>
  HostName <hostname>
  User <user>
  IdentityFile ~/.ssh/<key-name>
  IdentitiesOnly yes
  ProxyCommand cloudflared access ssh --hostname %h
  ServerAliveInterval 30
  ServerAliveCountMax 3
```

Hermes should prefer using a **stable alias** instead of a raw IP in later project files.

### Step 4: Register the public key on the remote host

Preferred order:

1. `ssh-copy-id` using the new alias or direct target
2. if that is unavailable or unsuitable, perform a one-time manual login and append the public key safely

Preferred automated path:

```bash
ssh-copy-id -i ~/.ssh/<key-name>.pub <alias-or-user@host>
```

Manual fallback:

1. show the public key locally:

```bash
cat ~/.ssh/<key-name>.pub
```

2. log into the server once
3. ensure remote permissions:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

4. append the public key if it is not already present

When Hermes is guiding a manual fallback, it should be explicit that the public key goes into:

- `~/.ssh/authorized_keys`

and that the file must not be replaced wholesale.

### Step 5: Verify non-interactive login

After key registration, verify:

```bash
ssh -o BatchMode=yes <alias> 'echo __SSH_KEY_OK__'
```

Success means:

- no password prompt
- command returns `__SSH_KEY_OK__`

If the host uses Cloudflare or another proxy layer and the first attempt fails intermittently, Hermes should:

- retry a small number of times
- capture the exact error
- distinguish between
  - transport failure
  - proxy failure
  - authentication failure

Do not declare success if the host still requires manual password entry.

### Step 6: Hand off to project operations

Once the host is verified, Hermes should record the reusable connection data in project control files.

For `remote-ssh` projects, `PROJECT.md` should include at least:

- `Execution Mode: remote-ssh`
- `SSH Host: <alias>`
- `SSH User: <user>`
- `Remote Project Root: ...`
- `Remote Worktree Root: ...` if applicable
- `Auth Mode: ssh-key`

If the project is managed by `software-control-tower`, Hermes should use the alias from this onboarding step instead of a raw IP.

---

## Output Contract

When this skill completes, Hermes should summarize:

- chosen SSH alias
- chosen key path
- whether the key was newly generated or reused
- whether the public key was registered successfully
- whether BatchMode verification succeeded
- any remaining manual step, if setup is not yet complete

If the host is tied to a project, Hermes should also produce a ready-to-use `PROJECT.md` snippet or confirm that the relevant remote fields were updated.

---

## Failure Handling

If onboarding fails, Hermes should say **which layer failed**:

- local key generation
- local SSH config
- transport / DNS / Cloudflare proxy
- remote login
- remote `authorized_keys` registration
- BatchMode verification

Do not collapse all of these into "SSH failed".

---

## Integration with Software Control Tower

After this skill succeeds, `software-control-tower` should be able to assume:

- the SSH alias is stable
- the host supports non-interactive key login
- remote-ssh project execution can use that alias

This skill prepares the runway.

`software-control-tower` should use the runway, not rebuild it.

