# Commit Message Rules

```
type(scope): short imperative subject under 72 chars

Body (recommended for `feat`, `fix`, `refactor`):
- Why: why this change is needed
- Behavior: what contract or behavior changed
- Refs: issue/PR references if applicable
- BREAKING CHANGE: migration notes if applicable

Refs: #123
BREAKING CHANGE: migration steps here (if any)
```

Types: feat, fix, refactor, docs, test, ci, deps
Scopes: cli, sources, store, query, domain, app, docs, test, ci, deps, governance

- `feat` and `fix` require a scope.
- `docs`, `test`, `ci`, `deps`, `refactor` may omit scope.
- Imperative mood, no trailing period, max 72 chars.
- Body required for `feat`, `fix`, `refactor`; explain why and the behavior or contract change.
- Footer: `Refs: #N`, `Fixes: #N`, `BREAKING CHANGE:`.
- **NO AI/AGENT TRAILERS**: Do not include `Co-authored-by`, `Ultraworked with`, or similar trailers for AI agents or automated tools.
