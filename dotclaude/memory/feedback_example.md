---
name: Integration tests must hit a real database
description: Never mock the DB in integration tests — prior incident
type: feedback
---

# Integration tests must hit a real database, not mocks

**Rule**: In integration tests, use a real database (docker-compose postgres
or equivalent). Do not replace it with mocks or fakes.

**Why**: Last quarter, a set of mocked tests passed on CI while a production
migration silently broke foreign-key constraints. The mock did not replicate
real schema behavior, so the failure only surfaced during the rollout.

**How to apply**: When writing or reviewing any test file under
`tests/integration/`, flag any use of `unittest.mock.patch` on DB modules.
Unit tests (`tests/unit/`) are allowed to mock freely — this rule is scoped
to integration tests only.
