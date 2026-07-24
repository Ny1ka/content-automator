"""Wires up the env vars DaVinciResolveScript.py needs before it can be imported.

Must run before `import DaVinciResolveScript` anywhere in the process — the module
resolves RESOLVE_SCRIPT_LIB via a C extension load at import time, not lazily.
"""
import os
import sys

_MAC_API_PATH = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
_MAC_LIB_PATH = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"


def ensure_resolve_env() -> None:
    if sys.platform != "darwin":
        raise RuntimeError(
            "resolve_env only knows the macOS install paths — add Windows/Linux "
            "paths here before running the real Resolve backend on those platforms."
        )
    os.environ.setdefault("RESOLVE_SCRIPT_API", _MAC_API_PATH)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", _MAC_LIB_PATH)
    modules_path = os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules")
    if modules_path not in sys.path:
        sys.path.append(modules_path)
