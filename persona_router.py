"""
persona_router.py

Drop-in persona/personality router for Hermes.

This module is intentionally self-contained and dependency-free (stdlib only)
so it can be wired into Hermes regardless of whether the existing CLI uses
argparse, click, or a custom dispatcher. It does not assume anything about
Hermes' internals beyond: "there is a point where a user message string is
about to be sent to the model, and you can intercept it there."

WHAT IT DOES
1. Detects a leading "/personality <name>" command in a message.
   - If found: switches the active persona, persists it to a state file,
     and returns a short confirmation (no model call needed for this turn).
2. On every other message, loads the currently active persona (if any) from
   the state file and prepends its system content to whatever system
   prompt / context Hermes already builds.
3. Supports "/personality" with no args (show current + list available) and
   "/personality off" / "/personality none" (clear persona).

WHERE STATE LIVES
~/.hermes/state/active_persona.txt
    Plain text file containing just the active persona name, e.g. "architect".
    Empty or missing file == no persona active (default Hermes behavior).

WHERE PERSONAS LIVE
~/.hermes/personalities/<name>.md
    Each file's full contents become the persona's system-prompt injection.

HOW TO WIRE THIS IN
You need exactly one integration point: wherever Hermes currently takes the
raw user input and either (a) dispatches it as a command, or (b) sends it to
the model as a chat message. See the bottom of this file for three concrete
wiring patterns (argparse, click, custom dispatch) -- use whichever matches
what `hermes --help` / reading hermes_cli/*.py shows you actually have.

This file has no external imports beyond the Python standard library, so it
will work regardless of what's already installed in the Hermes venv.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration -- adjust HERMES_HOME if Hermes is not installed at ~/.hermes
# ---------------------------------------------------------------------------

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
PERSONALITIES_DIR = HERMES_HOME / "personalities"
STATE_DIR = HERMES_HOME / "state"
ACTIVE_PERSONA_FILE = STATE_DIR / "active_persona.txt"

COMMAND_PREFIX = "/personality"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PersonaCommandResult:
    """Result of handling a /personality command.

    handled=True means: this message WAS a /personality command. Do not send
    it to the model. Show `reply` to the user instead (or pipe it through
    however Hermes normally prints command output).
    """
    handled: bool
    reply: Optional[str] = None


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def list_personas() -> list[str]:
    """Return sorted list of available persona names (filenames without .md)."""
    if not PERSONALITIES_DIR.is_dir():
        return []
    return sorted(
        p.stem for p in PERSONALITIES_DIR.glob("*.md") if p.is_file()
    )


def get_active_persona() -> Optional[str]:
    """Return the currently active persona name, or None if none is set."""
    if not ACTIVE_PERSONA_FILE.is_file():
        return None
    name = ACTIVE_PERSONA_FILE.read_text(encoding="utf-8").strip()
    return name or None


def set_active_persona(name: Optional[str]) -> None:
    """Set (or clear, if name is None) the active persona, persisted to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if name is None:
        if ACTIVE_PERSONA_FILE.exists():
            ACTIVE_PERSONA_FILE.unlink()
        return
    ACTIVE_PERSONA_FILE.write_text(name.strip() + "\n", encoding="utf-8")


def load_persona_content(name: str) -> Optional[str]:
    """Return the raw markdown content of a persona file, or None if missing."""
    path = PERSONALITIES_DIR / f"{name}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def get_active_persona_content() -> Optional[str]:
    """Convenience: load content for whichever persona is currently active.

    Returns None if no persona is active, or if the active persona's file
    has gone missing (e.g. renamed/deleted) -- in which case the state file
    is also cleared so we don't keep referencing a dead persona.
    """
    name = get_active_persona()
    if name is None:
        return None
    content = load_persona_content(name)
    if content is None:
        # Persona file vanished; self-heal by clearing the dangling state.
        set_active_persona(None)
        return None
    return content


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------

def _format_persona_list(current: Optional[str]) -> str:
    available = list_personas()
    if not available:
        return (
            f"No personas found in {PERSONALITIES_DIR}.\n"
            f"Add .md files there, e.g. {PERSONALITIES_DIR / 'architect.md'}"
        )
    lines = [f"Active persona: {current or '(none)'}", "", "Available:"]
    for p in available:
        marker = " <- active" if p == current else ""
        lines.append(f"  - {p}{marker}")
    lines.append("")
    lines.append("Usage: /personality <name>   (switch)")
    lines.append("       /personality off       (clear)")
    lines.append("       /personality            (show this list)")
    return "\n".join(lines)


def handle_message(message: str) -> PersonaCommandResult:
    """Inspect a raw user message; handle it if it's a /personality command.

    Call this FIRST, before any normal model dispatch. If handled=True, do
    not send the message to the model -- just show `reply` to the user.
    If handled=False, proceed with normal Hermes message handling as usual
    (optionally using get_active_persona_content() to inject persona context
    via inject_persona_into_system_prompt(), see below).
    """
    stripped = message.strip()

    if stripped != COMMAND_PREFIX and not stripped.startswith(COMMAND_PREFIX + " "):
        return PersonaCommandResult(handled=False)

    remainder = stripped[len(COMMAND_PREFIX):].strip()
    current = get_active_persona()

    # "/personality" alone -> show status + list
    if not remainder:
        return PersonaCommandResult(handled=True, reply=_format_persona_list(current))

    # "/personality off" / "/personality none" -> clear
    if remainder.lower() in ("off", "none", "clear", "reset"):
        if current is None:
            return PersonaCommandResult(handled=True, reply="No persona was active.")
        set_active_persona(None)
        return PersonaCommandResult(handled=True, reply=f"Persona cleared (was: {current}).")

    # "/personality <name>" -> switch
    requested = remainder.lower().replace(" ", "-")
    available = list_personas()
    if requested not in available:
        return PersonaCommandResult(
            handled=True,
            reply=(
                f"No persona named '{requested}'.\n\n"
                f"{_format_persona_list(current)}"
            ),
        )

    set_active_persona(requested)
    return PersonaCommandResult(handled=True, reply=f"Switched to persona: {requested}")


def inject_persona_into_system_prompt(base_system_prompt: str) -> str:
    """Given Hermes' normal system prompt string, prepend active persona content.

    If no persona is active, returns base_system_prompt unchanged. Safe to
    call on every turn -- it's just a file read + string concat.
    """
    persona_content = get_active_persona_content()
    if not persona_content:
        return base_system_prompt

    separator = "\n\n---\n\n"
    return persona_content + separator + base_system_prompt


# ---------------------------------------------------------------------------
# Self-test / CLI smoke test
# Run directly: python persona_router.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"HERMES_HOME      = {HERMES_HOME}")
    print(f"PERSONALITIES_DIR = {PERSONALITIES_DIR}")
    print(f"STATE_DIR        = {STATE_DIR}")
    print()
    print("Available personas:", list_personas() or "(none found)")
    print("Active persona:", get_active_persona() or "(none)")
    print()

    test_messages = [
        "/personality",
        "/personality architect",
        "what's the status of atlas",
        "/personality bogus-name",
        "/personality off",
    ]
    for msg in test_messages:
        result = handle_message(msg)
        print(f"> {msg}")
        if result.handled:
            print(f"  [handled] {result.reply}")
        else:
            print(f"  [not a command -- would dispatch normally]")
            sysprompt = inject_persona_into_system_prompt("BASE_SYSTEM_PROMPT_PLACEHOLDER")
            preview = sysprompt[:80].replace("\n", " ")
            print(f"  system prompt preview: {preview}...")
        print()
