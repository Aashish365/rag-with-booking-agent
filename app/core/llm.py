from __future__ import annotations
from typing import Any
from app.core.config import llm_config


def _get_client() -> Any:
    cfg = llm_config["llm"]
    provider = cfg["provider"]

    if provider in ("ollama", "openai"):
        from openai import AsyncOpenAI
        kwargs: dict[str, Any] = {"api_key": cfg.get("api_key", "ollama")}
        if cfg.get("base_url"):
            kwargs["base_url"] = cfg["base_url"]
        return AsyncOpenAI(**kwargs)

    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=cfg.get("api_key"))

    raise ValueError(f"Unknown LLM provider: {provider}")


async def chat_complete(messages: list[dict[str, str]]) -> str:
    cfg = llm_config["llm"]
    provider = cfg["provider"]
    model = cfg["model"]
    client = _get_client()

    if provider in ("ollama", "openai"):
        response = await client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content.strip()

    if provider == "anthropic":
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_msgs[0] if system_msgs else "",
            messages=user_msgs,
        )
        return response.content[0].text.strip()

    raise ValueError(f"Unknown provider: {provider}")
