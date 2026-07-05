# Personas Claude

Reusable Hermes/Claude persona prompts plus routing notes for Drew's local assistant stack.

## Persona files

| File | Purpose |
| --- | --- |
| `architect.md` | System design, planning, and tradeoff analysis. |
| `debugger.md` | Evidence-first troubleshooting and root-cause analysis. |
| `builder.md` | Implementation-focused coding and iterative delivery. |
| `homelab-admin.md` | Atlas, Docker, systemd, monitoring, and self-hosted operations. |
| `monday-consultant.md` | monday.com consulting, board design, automations, and client workflow support. |

## Router and wiring

| File | Purpose |
| --- | --- |
| `persona_router.py` | Chooses the best persona for a task based on prompt content. |
| `WIRING.md` | Notes for connecting the router into the live Hermes dispatch path. |

## Maintenance notes

- Keep persona changes small and reviewable; avoid broad tone rewrites unless intentionally reworking the persona.
- Update `WIRING.md` when router behavior or integration assumptions change.
- Test router edits with representative prompts before copying changes into the live Hermes profile.
