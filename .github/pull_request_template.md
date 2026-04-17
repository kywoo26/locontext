## Problem / Motivation
<!-- Why this change? Quantify if possible (e.g., "refresh emits 0 documents for valid pages"). -->

## Proposed Change
<!-- What changes at the contract/surface level? A reviewer should understand the impact without reading the diff. -->

## Alternatives Considered
<!-- What else did you consider and why was it rejected? Skip for trivial changes. -->

## Surfaces Touched
<!-- Check all that apply based on your change scope: -->
- [ ] CLI
- [ ] Sources / Refresh
- [ ] Store / Query
- [ ] Domain / App
- [ ] Docs / Governance
- [ ] CI / Build

## Verification
<!-- Run the subset from AGENTS.md that matches your surfaces. -->

**Always:**
- [ ] `uv run ruff check src/locontext tests`
- [ ] `uv run ty check`
- [ ] `uv run pytest`
- [ ] `uv run pytest -m integration`

**If CLI / refresh / store related:**
- [ ] `uv run locontext --help`

## Contract Sync
<!-- If you changed a surface, did you update its mirror? -->
- [ ] N/A (no surface change)
- [ ] AGENTS.md updated (rule / process change)
- [ ] README.md updated (user / developer surface change)
- [ ] docs/adr/ updated (architecture change)

## Risks / Rollback
<!-- Breaking changes? Migration notes? Performance regressions? Skip if none. -->
