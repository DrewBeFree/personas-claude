# Wiring persona_router.py into Hermes

This router is standalone and doesn't know anything about Hermes' internals.
You need to find ONE place in the Hermes codebase where a user's raw message
is about to be (a) checked for slash-commands, or (b) sent to the model --
and call into this router there.

## Step 0: figure out what you're dealing with

Run this on Atlas to see which pattern Hermes actually uses:

```bash
cd ~/.hermes/hermes-agent.full
grep -rn "argparse\|click\|ArgumentParser\|@click" hermes_cli/ | head -20
grep -rn "def.*dispatch\|def.*handle_message\|def.*process_message\|def.*on_message" hermes_cli/ agent/ | head -20
grep -rn "system_prompt\|system_message\|SOUL" hermes_cli/ agent/ | head -20
```

That'll tell you which of the three patterns below to use. Paste me the
output if you want help picking the exact integration point.

## Step 1: copy the files

```bash
mkdir -p ~/.hermes/personalities ~/.hermes/state
cp architect.md builder.md debugger.md homelab-admin.md monday-consultant.md \
   ~/.hermes/personalities/
cp persona_router.py ~/.hermes/hermes-agent.full/hermes_cli/   # or wherever makes sense
```

## Step 2: sanity check it works standalone

```bash
cd ~/.hermes/hermes-agent.full/hermes_cli   # or wherever you put it
python3 persona_router.py
```

You should see the 5 personas listed and a smoke test run through switching,
listing, bad-name handling, and clearing.

## Step 3: wire it in -- pick the pattern that matches your CLI

### Pattern A: argparse-based CLI

If Hermes uses argparse with a REPL-style loop reading input, find the loop
(probably something like `while True: msg = input(...)`) and wrap it:

```python
from persona_router import handle_message, inject_persona_into_system_prompt

while True:
    user_input = input("> ")

    # NEW: check for /personality commands first
    cmd_result = handle_message(user_input)
    if cmd_result.handled:
        print(cmd_result.reply)
        continue

    # existing Hermes code that builds the system prompt, then calls the model
    system_prompt = build_system_prompt()  # whatever Hermes already calls this
    system_prompt = inject_persona_into_system_prompt(system_prompt)  # NEW
    response = call_model(system_prompt, user_input)  # existing call
    print(response)
```

### Pattern B: click-based CLI

If commands are registered via `@click.command()`, add a sibling command and
intercept at the chat-message level instead (click commands are usually for
things like `hermes api`, not individual chat turns, so the chat loop is
probably still a plain Python loop somewhere -- same fix as Pattern A applies
to that loop). You likely don't need a new click command at all; the
`/personality` syntax is meant to be typed *into* the chat, not run as a
shell command.

### Pattern C: custom dispatch / message handler class

If there's a class like `MessageHandler` or `AgentSession` with a method like
`handle(message)` or `process(message)`, add the check at the top of that
method:

```python
from persona_router import handle_message, inject_persona_into_system_prompt

class MessageHandler:  # or whatever it's actually called
    def handle(self, message: str) -> str:
        cmd_result = handle_message(message)
        if cmd_result.handled:
            return cmd_result.reply

        system_prompt = self.build_system_prompt()
        system_prompt = inject_persona_into_system_prompt(system_prompt)
        return self.call_model(system_prompt, message)
```

## Step 4: test end to end

```
> /personality
(should list all 5 personas, none active)

> /personality debugger
Switched to persona: debugger

> hermes is showing a port conflict on 9119, what do i check first
(response should come back in the Debugger persona's terse, command-first style)

> /personality off
Persona cleared (was: debugger).
```

## Notes

- State lives in `~/.hermes/state/active_persona.txt` -- a single line of
  text. If you ever want per-conversation (not global) persona state instead
  of one global active persona, that's a bigger change (would need a
  conversation/session ID passed into the router) -- say the word if you
  want that version instead.
- The router self-heals if a persona file gets deleted/renamed while it's
  active -- it'll clear the dangling state rather than erroring.
- Adding a new persona later is just: drop a new `.md` file into
  `~/.hermes/personalities/`. No code changes needed.
