from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ensure_telegram_mock():
    import sys

    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    telegram_mod = MagicMock()
    telegram_mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    telegram_mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    telegram_mod.constants.ChatType.GROUP = "group"
    telegram_mod.constants.ChatType.SUPERGROUP = "supergroup"
    telegram_mod.constants.ChatType.CHANNEL = "channel"
    telegram_mod.constants.ChatType.PRIVATE = "private"

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, telegram_mod)


_ensure_telegram_mock()

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.platforms.telegram import TelegramAdapter
from gateway.session import SessionSource


def _message(text: str):
    return SimpleNamespace(
        text=text,
        caption=None,
        chat=SimpleNamespace(id=-100123, type="channel", title="Announcements"),
        from_user=None,
        reply_to_message=None,
        message_thread_id=None,
    )


def _event(text: str = "") -> MessageEvent:
    return MessageEvent(
        text=text,
        message_id="m1",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            user_id=None,
            chat_id="-100123",
            chat_name="Announcements",
            chat_type="channel",
        ),
    )


def _make_adapter():
    adapter = object.__new__(TelegramAdapter)
    adapter._should_process_message = MagicMock(return_value=True)
    adapter._clean_bot_trigger_text = lambda text: text
    adapter._enqueue_text_event = MagicMock()
    adapter.handle_message = AsyncMock()
    return adapter


def test_get_incoming_message_accepts_channel_post_but_not_edited_updates():
    adapter = _make_adapter()
    channel_post = _message("hello")

    assert adapter._get_incoming_message(
        SimpleNamespace(message=None, channel_post=channel_post)
    ) is channel_post
    assert adapter._get_incoming_message(
        SimpleNamespace(message=None, channel_post=None, edited_channel_post=channel_post)
    ) is None
    assert adapter._get_incoming_message(
        SimpleNamespace(message=None, edited_message=channel_post)
    ) is None


@pytest.mark.asyncio
async def test_text_handler_accepts_channel_post():
    adapter = _make_adapter()
    channel_post = _message("hello from channel")
    built_event = _event("hello from channel")
    adapter._build_message_event = MagicMock(return_value=built_event)

    await adapter._handle_text_message(
        SimpleNamespace(message=None, channel_post=channel_post),
        None,
    )

    adapter._build_message_event.assert_called_once_with(channel_post, MessageType.TEXT)
    adapter._enqueue_text_event.assert_called_once_with(built_event)


@pytest.mark.asyncio
async def test_command_handler_accepts_channel_post():
    adapter = _make_adapter()
    channel_post = _message("/help")
    built_event = _event("/help")
    adapter._build_message_event = MagicMock(return_value=built_event)

    await adapter._handle_command(
        SimpleNamespace(message=None, channel_post=channel_post),
        None,
    )

    adapter._build_message_event.assert_called_once_with(channel_post, MessageType.COMMAND)
    adapter.handle_message.assert_awaited_once_with(built_event)


@pytest.mark.asyncio
async def test_text_handler_ignores_edited_channel_post():
    adapter = _make_adapter()
    adapter._build_message_event = MagicMock()

    await adapter._handle_text_message(
        SimpleNamespace(message=None, channel_post=None, edited_channel_post=_message("edited")),
        None,
    )

    adapter._build_message_event.assert_not_called()
    adapter._enqueue_text_event.assert_not_called()
