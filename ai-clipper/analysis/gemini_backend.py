import os

from google import genai
from google.genai import types

import common.env  # noqa: F401 - loads .env before os.environ is read below

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (checked environment and .env).")
    return genai.Client(api_key=api_key)


def _to_plain(value):
    """Recursively convert genai's proto-backed Struct/MapComposite/ListComposite into
    plain dict/list/scalar so downstream code (pydantic validation, json.dump) doesn't
    need to know about protobuf types."""
    if hasattr(value, "items"):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)) or hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_to_plain(v) for v in value]
        except TypeError:
            return value
    return value


def call_tool_gemini(prompt: str, tool_name: str, schema: dict, model: str = DEFAULT_GEMINI_MODEL) -> dict:
    client = _client()
    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(name=tool_name, description=f"Submit the {tool_name} result.", parameters=schema),
    ])
    config = types.GenerateContentConfig(
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY", allowed_function_names=[tool_name]),
        ),
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=config)

    candidate = resp.candidates[0]
    fc = next((p.function_call for p in candidate.content.parts if p.function_call), None)
    if fc is None:
        raise RuntimeError(f"Gemini response had no function_call for '{tool_name}': {resp}")
    return _to_plain(fc.args)
