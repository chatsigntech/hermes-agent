"""Tests for human-approved outbound email replies."""

import json
import sys
import types
from pathlib import Path

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, SendResult
from gateway.session import SessionSource


@pytest.fixture(autouse=True)
def _mock_dotenv(monkeypatch):
    fake = types.ModuleType("dotenv")
    fake.load_dotenv = lambda *a, **kw: None
    monkeypatch.setitem(sys.modules, "dotenv", fake)


class _NotifyAdapter:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, content, **kwargs):
        self.sent.append({"chat_id": chat_id, "content": content, "kwargs": kwargs})
        return SendResult(success=True, message_id="notify-1")


class _EmailAdapter:
    def __init__(self):
        self.sent_text = []
        self.sent_images = []
        self.sent_docs = []
        self._thread_context = {
            "sender@example.com": {
                "subject": "Question",
                "message_id": "<orig@example.com>",
            }
        }

    @staticmethod
    def extract_media(content):
        return [], content

    @staticmethod
    def extract_images(content):
        return [], content

    @staticmethod
    def extract_local_files(content):
        return [], content

    async def _send_with_retry(self, chat_id, content, reply_to=None, **kwargs):
        self.sent_text.append({"chat_id": chat_id, "content": content, "reply_to": reply_to})
        return SendResult(success=True, message_id="email-1")

    async def send_image(self, chat_id, image_url, caption=None, reply_to=None, **kwargs):
        self.sent_images.append(
            {"chat_id": chat_id, "image_url": image_url, "caption": caption, "reply_to": reply_to}
        )
        return SendResult(success=True, message_id="img-1")

    async def send_document(self, chat_id, file_path, caption=None, reply_to=None, **kwargs):
        self.sent_docs.append(
            {"chat_id": chat_id, "file_path": file_path, "caption": caption, "reply_to": reply_to}
        )
        return SendResult(success=True, message_id="doc-1")


def _make_runner(tmp_path: Path):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.EMAIL: PlatformConfig(enabled=True, extra={"require_reply_approval": True}),
            Platform.TELEGRAM: PlatformConfig(enabled=True),
        }
    )
    runner.adapters = {
        Platform.EMAIL: _EmailAdapter(),
        Platform.TELEGRAM: _NotifyAdapter(),
    }
    runner._PENDING_EMAIL_REPLIES_PATH = tmp_path / "pending_email_replies.json"
    runner._pending_email_replies = {}
    return runner


def _email_event(text="hello") -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.EMAIL,
            chat_id="sender@example.com",
            user_id="sender@example.com",
            user_name="Sender",
        ),
        message_id="<orig@example.com>",
    )


def _telegram_command(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="7809026038",
            user_id="7809026038",
            user_name="Owner",
        ),
        message_id="tg-msg-1",
    )


@pytest.mark.asyncio
async def test_queue_email_reply_for_approval_notifies_telegram_allowlist(monkeypatch, tmp_path):
    runner = _make_runner(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "7809026038")

    queued = await runner._queue_email_reply_for_approval(
        _email_event(),
        "Here is the drafted reply.",
    )

    assert queued is True
    assert len(runner._pending_email_replies) == 1

    telegram_adapter = runner.adapters[Platform.TELEGRAM]
    assert len(telegram_adapter.sent) == 1
    sent = telegram_adapter.sent[0]
    assert sent["chat_id"] == "7809026038"
    assert "Pending email reply approval" in sent["content"]
    assert "/mailapprove" in sent["content"]
    saved = json.loads(runner._PENDING_EMAIL_REPLIES_PATH.read_text())
    assert len(saved) == 1


@pytest.mark.asyncio
async def test_mailapprove_sends_pending_email_and_clears_draft(tmp_path):
    runner = _make_runner(tmp_path)
    runner._pending_email_replies["abc123"] = {
        "chat_id": "sender@example.com",
        "content": "Approved body",
        "reply_to_message_id": "<orig@example.com>",
        "subject": "Question",
    }
    runner._save_pending_email_replies()

    response = await runner._handle_mailapprove_command(_telegram_command("/mailapprove abc123"))

    email_adapter = runner.adapters[Platform.EMAIL]
    assert email_adapter.sent_text == [
        {
            "chat_id": "sender@example.com",
            "content": "Approved body",
            "reply_to": "<orig@example.com>",
        }
    ]
    assert "abc123" not in runner._pending_email_replies
    assert json.loads(runner._PENDING_EMAIL_REPLIES_PATH.read_text()) == {}
    assert "Email draft `abc123` sent" in response


@pytest.mark.asyncio
async def test_maildeny_discards_pending_email(tmp_path):
    runner = _make_runner(tmp_path)
    runner._pending_email_replies["abc123"] = {
        "chat_id": "sender@example.com",
        "content": "Approved body",
        "reply_to_message_id": "<orig@example.com>",
        "subject": "Question",
    }
    runner._save_pending_email_replies()

    response = await runner._handle_maildeny_command(_telegram_command("/maildeny abc123"))

    assert "abc123" not in runner._pending_email_replies
    assert json.loads(runner._PENDING_EMAIL_REPLIES_PATH.read_text()) == {}
    assert "discarded" in response


def test_load_pending_email_replies_restores_saved_drafts(tmp_path):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._PENDING_EMAIL_REPLIES_PATH = tmp_path / "pending_email_replies.json"
    runner._PENDING_EMAIL_REPLIES_PATH.write_text(json.dumps({
        "abc123": {
            "chat_id": "sender@example.com",
            "content": "Draft body",
        }
    }))

    restored = runner._load_pending_email_replies()

    assert restored == {
        "abc123": {
            "chat_id": "sender@example.com",
            "content": "Draft body",
        }
    }


def test_load_pending_email_replies_ignores_corrupt_file(tmp_path):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._PENDING_EMAIL_REPLIES_PATH = tmp_path / "pending_email_replies.json"
    runner._PENDING_EMAIL_REPLIES_PATH.write_text("{not-json")

    assert runner._load_pending_email_replies() == {}
