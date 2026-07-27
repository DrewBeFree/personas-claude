# App Index

Quick navigation for Drew's reusable Hermes/Claude persona prompt repository.

| File | Purpose |
| --- | --- |
| `architect.md` | System design, planning, and tradeoff analysis persona. |
| `debugger.md` | Evidence-first troubleshooting and root-cause analysis persona. |
| `builder.md` | Implementation-focused coding and iterative delivery persona. |
| `homelab-admin.md` | Atlas, Docker, systemd, monitoring, and self-hosted operations persona. |
| `monday-consultant.md` | monday.com consulting, board design, automations, and client workflow support persona. |
| `persona_router.py` | Keyword-based router for selecting a persona from prompt content. |
| `WIRING.md` | Notes for connecting persona routing into Hermes dispatch. |

## Maintenance notes

- Keep persona edits narrow and reviewable.
- Update `README.md` and this index when adding, removing, or renaming persona files.
- Run router smoke tests after editing `persona_router.py`.
