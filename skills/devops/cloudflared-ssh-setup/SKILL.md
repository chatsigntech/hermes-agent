---
name: cloudflared-ssh-setup
description: Set up or maintain Cloudflare Tunnel based SSH access end-to-end, including server-side tunnel/ingress/DNS/service setup and client-side cloudflared plus SSH config for passwordless or proxy-based login.
---

# Cloudflared SSH Setup

Use this skill when a user wants to expose SSH through Cloudflare Tunnel, repair an existing Cloudflare-backed SSH path, or prepare a client machine to connect through `cloudflared access ssh`.

This skill covers both sides:
- **Server side**: install `cloudflared`, create or reuse a tunnel, add SSH ingress, route DNS, and run the service persistently.
- **Client side**: install `cloudflared`, configure `~/.ssh/config`, and verify login through the tunnel.

If the user already has one half done, only perform the missing half. Preserve existing tunnel topology unless the user explicitly wants a new tunnel.

## Decide the mode first

Before changing anything, identify which of these modes applies:

1. **New server onboarding**
   The server does not yet expose SSH through Cloudflare.
2. **Existing tunnel, missing SSH ingress**
   The tunnel already serves HTTP or webhook traffic and only needs SSH added.
3. **Client onboarding**
   The server is already configured; the client just needs `cloudflared` and SSH config.
4. **Repair / audit**
   The path exists but login fails intermittently or DNS / ingress / Access policy is unclear.

Do not create a second tunnel if the existing tunnel should simply gain one more hostname.

## Server-side workflow

### 1. Collect the minimum facts

Confirm or discover:
- Target hostname, for example `ssh.example.com`
- Tunnel name or UUID, if one already exists
- Whether this should reuse an existing tunnel
- Local SSH target on the server, usually `ssh://localhost:22`
- Whether the server is Linux or macOS
- Whether Cloudflare Access policy already exists for the hostname

If the hostname already belongs to a different machine, stop and ask before overriding DNS.

### 2. Install `cloudflared`

Server examples:

**macOS**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Debian / Ubuntu**
```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

### 3. Log in and create or reuse the tunnel

If no tunnel exists yet:
```bash
cloudflared tunnel login
cloudflared tunnel create <tunnel-name>
```

If a tunnel already exists:
```bash
cloudflared tunnel list
```

Prefer reusing the existing tunnel when the machine already serves other traffic and the user has not asked for hard isolation.

### 4. Add SSH ingress

Canonical config fragment:

```yaml
tunnel: <tunnel-uuid>
credentials-file: /home/<user>/.cloudflared/<tunnel-uuid>.json

ingress:
  - hostname: ssh.example.com
    service: ssh://localhost:22
  - service: http_status:404
```

If the file already has other routes, append the SSH hostname above the final `http_status:404` catch-all. Do not remove unrelated routes.

Common config locations:
- `~/.cloudflared/config.yml`
- `/etc/cloudflared/config.yml`

If both exist, keep them aligned.

### 5. Route DNS to the tunnel

```bash
cloudflared tunnel route dns <tunnel-name> ssh.example.com
```

If the DNS record already exists, verify it points at the intended tunnel before changing it.

### 6. Run `cloudflared` persistently

**Linux / systemd**
```bash
sudo cp ~/.cloudflared/config.yml /etc/cloudflared/config.yml
sudo cp ~/.cloudflared/<tunnel-uuid>.json /etc/cloudflared/
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```

**macOS / launchd**
If Cloudflare service install is available, prefer the vendor-managed service. Otherwise use a launch agent that starts:
```bash
cloudflared tunnel run <tunnel-name>
```

Do not create a second background service if one already manages the same tunnel.

### 7. Verify the server side

Check all of these:

```bash
cloudflared tunnel list
cloudflared tunnel info <tunnel-name>
cloudflared tunnel route dns
```

And verify local SSH is alive:
```bash
ssh localhost
```
or at least:
```bash
nc -z localhost 22
```

If the tunnel is healthy but local port 22 is closed, this is an SSH server problem, not a Cloudflare tunnel problem.

## Client-side workflow

### 1. Install `cloudflared`

**macOS**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Linux**
Use the same package install flow as above.

### 2. Add SSH config

Basic config:

```sshconfig
Host ssh.example.com
    User <remote-user>
    ProxyCommand cloudflared access ssh --hostname %h
```

Project-specific alias is often better than mutating the shared hostname entry:

```sshconfig
Host my-project-remote
    HostName ssh.example.com
    User <remote-user>
    ProxyCommand cloudflared access ssh --hostname %h
```

If the host also requires an SSH key, add:

```sshconfig
    IdentityFile ~/.ssh/<key-name>
    IdentitiesOnly yes
```

### 3. Verify the client side

Interactive test:
```bash
ssh <alias-or-hostname>
```

Non-interactive check:
```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 <alias-or-hostname> 'echo __SSH_OK__'
```

Interpretation:
- `__SSH_OK__` means the full path is working
- `Permission denied` means Cloudflare path is alive but SSH auth is not ready
- `Connection closed by UNKNOWN port 65535` often points to `cloudflared access ssh` instability or Access session issues
- timeout or route errors usually indicate DNS, tunnel, or local network problems

## Access policy and auth expectations

Cloudflare Tunnel and Cloudflare Access are separate concerns.

- Tunnel exposes the hostname to the origin service
- Access controls who may connect

If Access policy is enabled, expect browser-based sign-in on the client side before SSH succeeds. If the user wants fully unattended automation, verify whether the Access policy allows that flow; otherwise the path may stay interactive even when the tunnel is correct.

## Repair checklist

When a user says SSH is flaky or "sometimes works":

1. Verify the hostname resolves to the intended tunnel
2. Verify `cloudflared` service is actually running on the server
3. Verify the ingress still includes `ssh://localhost:22`
4. Verify local `sshd` is listening on the origin machine
5. On the client, test `cloudflared access ssh --hostname <host>` behavior
6. Then test `ssh -vvv <host-or-alias>`

Do not conclude "SSH is fine" from only checking `~/.ssh/config` or the existence of keys.

## Safety rules

- Do not overwrite an existing hostname that belongs to another machine without explicit approval.
- Do not create a second tunnel when one existing tunnel should be extended.
- Do not erase unrelated ingress routes from a shared tunnel config.
- Prefer project-specific SSH aliases when the user does not want a global behavior change.
- If the path is intended for automation, prefer SSH key login over password login.

## Output expectations

When finishing, report these concrete items:
- Tunnel name / UUID used
- SSH hostname configured
- Whether DNS was added or reused
- Whether the service is persistent and how it is managed
- Exact client-side SSH stanza to use
- Final verification result and the remaining blocker, if any
