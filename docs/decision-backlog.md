# Decision Backlog

This file tracks technical choices that are intentionally provisional or deferred.

Use ADRs for decisions that are already locked. Use this file for decisions that need a future re-evaluation trigger.

| Topic | Status | Current Direction | Revisit Trigger | Candidate Options |
| :--- | :--- | :--- | :--- | :--- |
| CLI framework | Provisional | `click` | command tree or CLI complexity grows beyond a thin adapter | `click`, `argparse` |
| HTTP retry policy | Deferred | no dedicated retry library yet | real network fetch path with repeated transient failure handling needs | local helper, `tenacity` |
| Settings library | Deferred | stdlib `tomllib` + dataclass loader | env/config layering or nested validation becomes materially more complex | current approach, `pydantic-settings` |
| SQL migration tool | Deferred | keep raw SQL and add a small local migration runner | schema churn becomes frequent enough that local migration maintenance becomes noisy | local runner, `yoyo-migrations` |
| SQL abstraction layer | Deferred | direct `sqlite3` + explicit SQL | query construction becomes significantly more dynamic or repetitive | current approach, `SQLAlchemy Core` |
| Structured LLM output helper | Deferred | provider SDK + typed local boundary if needed | multiple structured-output integrations make provider-specific code repetitive | provider-native models, `instructor`, `pydantic` |
| Token counting | Deferred | none for v1 core | prompt budgeting becomes a real runtime concern | none, `tiktoken` |
| MCP / agent transport | Deferred | keep CLI/app seam transport-agnostic | first stable external tool/resource integration path is defined | plain CLI contract, official MCP SDK |
| Multi-provider LLM abstraction | Deferred | use official provider SDKs directly if/when needed | two or more providers become a real product requirement | direct SDKs, LiteLLM SDK |
