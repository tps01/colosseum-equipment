# AGENTS.md

Baseline expectations for AI agents in this plugin repository.

## Purpose

- This is a first-party Colosseum plugin. Development, packaging, and usage follow the same entry-point contract as third-party plugins.
- Depends on `colosseum-core` and `colosseum-shared` as declared in `pyproject.toml`.
- Registers `equipment` and `io` namespaces; public API includes `col.equipment.autoconfig()`.

## Change discipline

Prefer focused, compact changes. Do not commit unless asked. Read `RULES.md` at task start.

## Workflow

When completing changes, increment the package version in `pyproject.toml` and `__version__` using semantic versioning. Agents cannot increment the major number.
