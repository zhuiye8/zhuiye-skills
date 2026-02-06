---
name: format-doc
description: Deterministic documentation formatting and synchronization for code changes. Use this skill when creating, editing, deleting, moving, or renaming source files; when users ask to "update docs", "sync docs with code", "auto-doc", or "format documentation"; or when maintaining ARCHITECTURE.md, folder INDEX.md files, and file-level input/output header comments.
---

# Format Doc

Maintain code documentation as a derived artifact of code changes.
Apply delta-first updates so documentation stays accurate without unnecessary rewrites.

## Core Outcomes

Maintain the following three tiers:

1. Root `ARCHITECTURE.md`
2. Folder-level `INDEX.md` for folders that contain source files
3. File-level header comments describing `@input`, `@output`, and `@position`

## Non-Negotiable Rules

1. Update documentation after every relevant code change.
2. Update only the affected scope unless a structural change requires broader updates.
3. Keep summaries concise and factual.
4. Never invent behavior not supported by code.
5. If documentation files are missing, create minimal valid versions.

## Change Classification

Classify each change first, then decide required updates.

| Change type | Typical examples | Header update | Folder INDEX.md | ARCHITECTURE.md |
|---|---|---|---|---|
| Logic-only internal change | Refactor internals, bug fix without contract changes | If `@input/@output/@position` changed | If file role changed materially | No |
| Contract or dependency change | New export, changed API shape, new external dependency | Yes | Yes | If cross-folder dependency flow changed |
| File create/delete | Add/remove source file | New file: yes | Yes | If this introduces/removes a module capability |
| Rename/move | File renamed or moved folders | Yes | Source + target folder | If module boundaries changed |
| Structural architecture change | New domain folder, merged components, changed layers | Yes where impacted | Yes | Yes |

## Scope and Exclusions

Apply to source files and architecture docs.
Do not update headers or indexes for:

- Generated files and build artifacts
- Third-party/vendor code
- Lockfiles and dependency snapshots
- Binary files
- Temporary, cache, and tooling output directories

Common ignore examples:
`.git/`, `node_modules/`, `dist/`, `build/`, `target/`, `coverage/`, `vendor/`, `.next/`, `out/`.

## Required Formats

### Tier 1: Root ARCHITECTURE.md

Use this structure:

```markdown
<!-- FORMAT-DOC: Update when project structure or architecture changes -->

# Architecture

<Up to 10 lines: high-level architecture and dependency flow>

## Modules

- [module-a](module-a/INDEX.md) - <1-line responsibility>
- [module-b](module-b/INDEX.md) - <1-line responsibility>
```

Requirements:

1. Keep overview short and structural.
2. Link all major code modules with their `INDEX.md`.
3. Reflect only current structure.

### Tier 2: Folder INDEX.md

Use this structure:

```markdown
<!-- FORMAT-DOC: Update when files in this folder change -->

# <FolderName>

<1-3 line folder responsibility summary>

## Files

| File | Role | Responsibilities |
|---|---|---|
| example.ts | Service | Handles user authentication flow |
```

Requirements:

1. One row per maintained source file.
2. Use concrete role labels like `Controller`, `Service`, `Repository`, `Schema`, `UI`.
3. Remove stale rows immediately when files are deleted/moved.

### Tier 3: File Header Comments

Use these required fields:

- `@input`: external dependencies consumed by this file
- `@output`: exports, side effects, or delivered capabilities
- `@position`: why this file exists in local architecture
- `@doc-sync`: reminder to sync header + folder index

TypeScript/JavaScript:

```typescript
/**
 * @input { UserRepo } from './repo/user-repo', { env } from '@/config/env'
 * @output { createUserService, UserService } user-domain service API
 * @position Application service layer for user lifecycle orchestration
 * @doc-sync Update this header and folder INDEX.md when this file changes.
 */
```

Python:

```python
"""
@input: requests, json; Settings from .config
@output: Client class for upstream API communication
@position: Infrastructure adapter for external HTTP APIs
@doc-sync: Update this header and folder INDEX.md when this file changes.
"""
```

Go:

```go
// @input: net/http, context; UserService from internal/service
// @output: Handler, NewHandler(), ServeHTTP()
// @position: HTTP transport adapter for user endpoints
// @doc-sync: Update this header and folder INDEX.md when this file changes.
```

Java:

```java
/**
 * @input UserRepository from com.example.user.repo; Clock from java.time
 * @output UserService, createUser(), deactivateUser()
 * @position Application service coordinating user lifecycle use cases
 * @doc-sync Update this header and folder INDEX.md when this file changes.
 */
```

## Execution Workflow

Run in this order after each relevant change:

1. Identify changed source files and classify changes.
2. Update file headers where contracts/dependencies/position changed.
3. Update impacted folder `INDEX.md` files.
4. Update root `ARCHITECTURE.md` only for structural or dependency-flow changes.
5. Validate consistency and remove stale documentation entries.

## Consistency Checks

Before finishing, verify:

1. Every changed source file has a valid header format.
2. Every indexed file actually exists in its folder.
3. Every changed folder with source files has an up-to-date `INDEX.md`.
4. `ARCHITECTURE.md` links point to existing `INDEX.md` files.
5. No deleted or moved files remain in docs.

## Built-in Checker Script

Use `scripts/check_format_doc.py` for deterministic checks in local and CI flows.

Supported extensions by default:

- `.js`, `.jsx`, `.mjs`, `.cjs`
- `.ts`, `.tsx`
- `.py`
- `.go`
- `.java`

Common commands:

```bash
# Full repository check
python format-doc/scripts/check_format_doc.py --root .

# Check only changed files (git working tree + untracked)
python format-doc/scripts/check_format_doc.py --root . --mode changed

# Check staged files only (for pre-commit)
python format-doc/scripts/check_format_doc.py --root . --mode staged

# Extend to other languages in mixed stacks
python format-doc/scripts/check_format_doc.py --root . --ext .rb --ext .php
```

For repositories not ready for full three-tier enforcement yet, temporarily use:

```bash
python format-doc/scripts/check_format_doc.py --root . --allow-missing-architecture
```

## Decision Guardrails

1. Prefer minimal diffs over broad rewrites.
2. Preserve existing naming conventions and terminology.
3. If uncertain, infer `@input/@output` from imports, exports, function signatures, and call graph.
4. If uncertainty remains, mark assumptions explicitly in one concise note in the user response.
5. If user explicitly says to skip documentation updates, follow the user instruction and state the risk briefly.
6. For document language, use this priority: explicit user preference > repository conventions > Chinese default.
7. Keep language consistent across header comments, folder indexes, and architecture docs in the same update.

## Recommended Automation Hooks

If repository automation is requested, add:

1. A pre-commit check that rejects stale `INDEX.md` entries.
2. A CI check that verifies architecture links and header presence.
3. A lightweight script that validates the three-tier invariants from changed files.

Keep automation deterministic and fast so it runs in local workflows and CI.
