"""
Claude API client wrapper.
Provides sync + async helpers, streaming, and tool use.
"""
from __future__ import annotations
import os
import json
from typing import AsyncIterator, Optional, Any

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


MODEL = "claude-opus-4-5"
FAST_MODEL = "claude-haiku-4-5"

def _get_client() -> "anthropic.Anthropic | None":
    if not _ANTHROPIC_AVAILABLE:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _get_async_client() -> "anthropic.AsyncAnthropic | None":
    if not _ANTHROPIC_AVAILABLE:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.AsyncAnthropic(api_key=api_key)


def complete(
    prompt: str,
    system: str = "",
    model: str = MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> Optional[str]:
    """Synchronous completion."""
    client = _get_client()
    if not client:
        return None
    msgs = [{"role": "user", "content": prompt}]
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=msgs,
    )
    return resp.content[0].text if resp.content else None


async def acomplete(
    prompt: str,
    system: str = "",
    model: str = MODEL,
    max_tokens: int = 2048,
    messages: Optional[list] = None,
    temperature: float = 0.0,
) -> Optional[str]:
    """Async completion."""
    client = _get_async_client()
    if not client:
        return None
    msgs = messages or [{"role": "user", "content": prompt}]
    resp = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=msgs,
    )
    return resp.content[0].text if resp.content else None


async def astream(
    prompt: str,
    system: str = "",
    model: str = MODEL,
    max_tokens: int = 2048,
    messages: Optional[list] = None,
    temperature: float = 0.0,
) -> AsyncIterator[str]:
    """Async streaming completion – yields text chunks."""
    client = _get_async_client()
    if not client:
        yield "[AI assistant unavailable – set ANTHROPIC_API_KEY]"
        return
    msgs = messages or [{"role": "user", "content": prompt}]
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=msgs,
    ) as stream:
        async for chunk in stream.text_stream:
            yield chunk


def is_available() -> bool:
    return _ANTHROPIC_AVAILABLE and bool(os.getenv("ANTHROPIC_API_KEY"))
