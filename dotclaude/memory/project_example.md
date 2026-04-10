---
name: Auth middleware rewrite — compliance driven
description: Reason for the auth rewrite is legal/compliance, not tech debt
type: project
---

# Auth middleware rewrite is compliance-driven

**Fact**: The ongoing rewrite of the auth middleware is driven by
legal/compliance requirements around session-token storage, not by
technical-debt cleanup.

**Why**: Legal flagged the current implementation for storing session tokens
in a way that fails the new compliance audit. Deadline: 2026-06-30.

**How to apply**: When the user asks for scope trade-off decisions on this
rewrite, favor compliance correctness over ergonomics or backward-compat.
Breaking changes to internal APIs are acceptable; deviations from the
compliance spec are not.
