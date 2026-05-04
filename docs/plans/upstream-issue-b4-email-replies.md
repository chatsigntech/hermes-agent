# Upstream Issue Draft — Approved Email Replies + File Attachments (B4)

To be filed at: https://github.com/nousresearch/hermes-agent/issues/new

Below is the proposed issue body. Trim/edit before posting.

---

## Title

`feat: approved email replies + file attachments via gateway`

## Body

### Summary

Hermes currently lets the agent post replies to chat platforms (Telegram, Slack,
WeChat, etc.) on its own. But for **email**, sending a reply on the agent's own
authority can be high-stakes: an agent-written response to a real human reaches
business contacts, family, banks, schools — places where the user generally
wants to vet the wording before it goes out.

This issue proposes a **human-in-the-loop email reply** flow plus the ability
to attach local files to outbound email, so the agent can draft, the user can
approve, and the gateway sends.

### User-visible behavior

1. Agent decides "I should reply to this email" → it calls a tool to **draft**
   a reply (subject, body, optional attachments).
2. Gateway stores the draft as **pending** with a `draft_id`.
3. Gateway notifies the user (via the configured approval channel — could be
   the same email thread, or a chat platform like Telegram) with the draft
   contents and an action prompt: `/mailapprove <draft_id>` or
   `/maildeny <draft_id>`.
4. User runs `/mailapprove`. Gateway sends the email (with attachments).
5. User runs `/maildeny`. Gateway discards the draft.

Drafts persist across gateway restarts so a user who is away for hours doesn't
lose the queue.

### Why this is generally useful

- Email is one of the most user-facing surfaces an LLM agent touches; the
  failure modes (sending to wrong recipient, wrong tone, hallucinated facts)
  are higher cost than chat
- File attachments are commonly needed (e.g. agent generates a PDF / chart /
  CSV and sends it as part of a reply); currently no gateway-level support
- The persistence aspect ("drafts survive restart") is a generic property of
  any approval-mediated outbound action, useful beyond email

### Implementation sketch (preliminary)

Roughly four logical pieces, suggesting four PRs:

1. **Config schema** — `gateway.config` adds:
   - `email.require_reply_approval: bool` (default true)
   - `email.approval_platform: str`  (which platform to notify; default: same email thread)
   - `email.approval_chat_id: str`  (target id on that platform)

2. **Platform base class** — extend `gateway/platforms/base.py` so non-text
   platforms can express that an outbound message includes file attachments
   (currently the abstraction is text-only).

3. **Gateway runner main flow** — `gateway/run.py` adds:
   - `_pending_email_replies` state dict (persisted to
     `~/.hermes/pending_email_replies.json`, atomic writes)
   - new tool: `email_draft_reply` (input: thread_id, subject, body, attachments)
   - approval/deny handlers wired to `/mailapprove` / `/maildeny`
   - approval channel routing logic

4. **CLI command** — `hermes mail` subcommand surface:
   - `hermes mail pending` — list pending drafts
   - `hermes mail approve <draft_id>` — approve from CLI (companion to chat-platform action)
   - `hermes mail deny <draft_id>` — deny

A working local prototype exists at `chatsigntech/hermes-agent` —
[commit `58fb4a09`](https://github.com/chatsigntech/hermes-agent/commit/58fb4a09).
Happy to break it into smaller PRs once the design here is approved. The
companion persistence change `e6775c0c fix(gateway): persist pending email reply
approvals` adds atomic-write durability to the drafts dict and would likely
go in alongside (3).

### Open questions for maintainers

1. Is "approved replies" generally desired in upstream, or is it considered a
   user-specific workflow that should live in a plugin / fork?
2. Should the approval mechanism reuse the existing pairing/approval
   primitives (where present), or get its own `/mailapprove` namespace?
3. Attachments: file size cap? sanitize/scan local paths before sending?
4. For approval-channel notifications, should the gateway depend on a
   configured chat platform being live, or fail closed (don't send if no
   approval channel reachable)?

### Out of scope for this issue

- Outbound email *initiation* (agent composing email to a fresh recipient
  without an inbound trigger) — separate, larger scope
- Calendar invitations, RSVPs — handle in their own issues
- IMAP folder management (move-to-archive, label, etc.) — not core to this

---

## Filing checklist (before clicking submit on GitHub)

- [ ] Issue title is concise (`feat: approved email replies + file attachments via gateway`)
- [ ] Body trimmed of editorial content (this header doc, the "before posting" notes)
- [ ] Local commit reference uses correct GitHub permalink format
- [ ] Maintainer mentions removed (don't `@`-tag specific people on a fresh issue)
- [ ] Choose label set if maintainers expect one (`enhancement`, `gateway`, `email`)

## After filing

Update `docs/plans/upstream-sync-strategy.md` § 4 with the issue URL.
Wait for maintainer triage (typically 3–7 days). Do not start the 4 sub-PRs
until you get a "yes, please proceed" / "split it this way instead" signal.

If maintainers say "no, this lives in a plugin / fork":
- Move B3 + B4 commits to E class (self-maintained)
- Document the plugin boundary in `skills/` if it makes sense as an opt-in skill
