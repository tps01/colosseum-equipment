# AGENTS.md

Baseline expectations for AI agents in this plugin repository.

## Purpose

- This is a first-party Colosseum plugin. Development, packaging, and usage
  follow the same entry-point specification as third-party plugins.
- Depends only on `colosseum-core` as declared in `pyproject.toml` (plugins must
  not depend on each other).
- Registers `equipment` and `io` namespaces; public API includes
  `col.equipment.autoconfig()`.

## Change discipline

Prefer focused, compact changes. Do not commit unless asked. Read `RULES.md` at
task start.

One config row uses `[dotted.path]`. Use `[[dotted.path]]` only when the sample
shows multiple rows of that same section. Do not use array-of-tables syntax as
the default for a single instrument, profile, or service.

When a test fails, reproduce the bug before fixing it. Understand why it is
failing before addressing it. Do not adjust tests purely to obtain passing
results. Write the least code that works, and spend the effort to reach that;
it is more effective in the long run. When possible, substantiate claims with
evidence such as plots, tracebacks, or links.

## Footprint

Follow the workspace **Minimizing footprint** section (top-level `AGENTS.md`).
Inventory
existing code before adding files; prefer merge, relocate, or delete over new
modules.
Keep plugin-only helpers local (e.g. `_paths.py`, `_cache.py`). Do not expand
core for
single-plugin needs.

## Workflow

When completing changes, increment the package version in `pyproject.toml` using
semantic versioning. Agents cannot increment the major number.

When finishing a development session: `python scripts/cleanup.py --dry-run`,
then
`python scripts/cleanup.py` if the list looks right. See workspace `AGENTS.md`
(**Simulated annealing**, **End-of-development cleanup**).
