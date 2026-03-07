"""Telegram sender for daily review report."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List

import requests

from modules.daily_review.config import DailyReviewConfig, TELEGRAM_CONFIG

logger = logging.getLogger(__name__)

_MDV2_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def _escape_markdown_v2(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    for ch in _MDV2_SPECIAL:
        escaped = escaped.replace(ch, f"\\{ch}")
    return escaped


def _simplify_markdown(markdown_text: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", markdown_text, flags=re.MULTILINE)
    text = text.replace("**", "")
    text = text.replace("`", "")
    text = re.sub(r"^\|[-\s:|]+\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_chunks(text: str, max_length: int) -> List[str]:
    sections = text.split("\n---\n")
    chunks: List[str] = []
    current = ""

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        candidate = f"{current}\n---\n{sec}".strip() if current else sec
        if len(candidate) <= max_length:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(sec) > max_length:
            chunks.append(sec[:max_length])
            sec = sec[max_length:]
        if sec:
            current = sec

    if current:
        chunks.append(current)
    return chunks or [text[:max_length]]


def _send_once(api_url: str, payload: dict) -> requests.Response:
    return requests.post(api_url, json=payload, timeout=15)


async def _post_with_retry(api_url: str, payload: dict, max_retries: int = 3) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            response = await asyncio.to_thread(_send_once, api_url, payload)
        except requests.RequestException as exc:
            if attempt == max_retries:
                logger.warning("Telegram request failed after retries: %s", exc)
                return False
            await asyncio.sleep(2 ** (attempt - 1))
            continue

        if response.status_code == 200 and response.json().get("ok"):
            return True

        if response.status_code == 429:
            retry_after = 2
            try:
                retry_after = int(response.json().get("parameters", {}).get("retry_after", 2))
            except Exception:
                retry_after = 2
            if attempt < max_retries:
                await asyncio.sleep(retry_after)
                continue

        if response.status_code >= 500 and attempt < max_retries:
            await asyncio.sleep(2 ** (attempt - 1))
            continue

        logger.warning("Telegram send failed (status=%s): %s", response.status_code, response.text[:200])
        return False

    return False


async def send_review(report_markdown: str, config: DailyReviewConfig) -> bool:
    """Send review markdown by Telegram Bot with MarkdownV2 escaping and chunking."""

    bot_token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not bot_token or not chat_id:
        logger.info("Telegram token/chat_id not configured, skip sending.")
        return False

    max_length = TELEGRAM_CONFIG["max_message_length"]
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    plain_text = _simplify_markdown(report_markdown)
    chunks = _split_chunks(plain_text, max_length=max_length)

    ok = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": _escape_markdown_v2(chunk),
            "parse_mode": TELEGRAM_CONFIG["parse_mode"],
            "disable_web_page_preview": True,
        }
        sent = await _post_with_retry(api_url, payload, max_retries=3)
        ok = ok and sent
    return ok
