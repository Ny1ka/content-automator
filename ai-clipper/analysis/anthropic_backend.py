import os

import anthropic

import common.env  # noqa: F401 - loads .env before os.environ is read below

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Layer 2 needs a pay-as-you-go Anthropic API key "
            "(separate from a Claude.ai/Claude Code subscription) — set it in your shell "
            "or in .env before running analysis with provider='anthropic'."
        )
    return anthropic.Anthropic()


def call_tool_anthropic(prompt: str, tool_name: str, schema: dict, model: str = DEFAULT_ANTHROPIC_MODEL) -> dict:
    client = _client()
    resp = client.messages.create(
        model=model,
        max_tokens=8192,
        tools=[{"name": tool_name, "description": f"Submit the {tool_name} result.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError(f"Anthropic response had no tool_use block for '{tool_name}'")
    return tool_use.input
