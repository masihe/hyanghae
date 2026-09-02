# AGENTS.md

## Project Context

This repository is a Python/Jupyter-based perfume data analysis and recommendation project.

The project contains:
- raw perfume data
- exploratory and validation notebooks
- analysis outputs
- evaluation data
- reusable scent-knowledge data

Follow the global AGENTS.md rules first.
This file adds only project-specific constraints.

## Project Priorities

1. Preserve reproducibility.
2. Reuse existing analysis before creating new analysis.
3. Keep analysis scope tied to a concrete product or model decision.
4. Keep reusable data separate from temporary analysis output.
5. Prefer small, understandable notebook changes over large pipelines.

## Data Protection

Treat the following as source data unless the user explicitly requests otherwise:

- `perfumes.csv`
- `perfumes.jsonl`
- `SCHEMA.md`
- `evaluation_data/`
- raw files under `data/**/raw/`

Do not:
- overwrite source data
- silently normalize source data in place
- move or rename source files
- change existing evaluation labels without explicit instruction

Create derived data separately when needed.

## Existing Work First

Before creating a new notebook, script, dataset, or analysis:

1. inspect relevant existing notebooks
2. inspect relevant files in `analysis_outputs/`
3. inspect reusable data under `data/`
4. determine whether the question has already been answered

If an existing result is sufficient, reuse it.

Do not recompute an existing result solely to produce another copy.

## Notebook Scope

A notebook should answer one clear question.

Do not expand a notebook with unrelated:
- statistics
- visualizations
- models
- data exports
- robustness checks

unless they are required to answer that question.

If additional analysis would be useful but is not required, propose it instead of implementing it.

## Output Discipline

Create a new output file only when it is one of the following:

1. reusable project data
2. required input for a later confirmed task
3. a requested final report or deliverable

Prefer notebook output for:
- temporary inspection
- debugging
- one-time summary statistics
- intermediate tables

Do not export every intermediate dataframe to CSV.

## Reusable Data vs Analysis Output

Use project locations according to their role:

### `data/`
Store data intended to be reused by later code or analysis.

Examples:
- processed external datasets
- scent knowledge dictionaries
- validated mappings

### `analysis_outputs/`
Store analysis-specific results that support a decision or document an experiment.

Do not treat every analysis output as permanent runtime data.

## Analysis Rules

### Reuse established results

Do not rerun or redesign earlier experiments unless:
- the user explicitly asks, or
- a newly discovered issue invalidates the previous result

### Do not optimize a metric for its own sake

Metrics such as coverage, accuracy, similarity, or retrieval scores are evaluation tools.

Do not weaken semantic or data-quality rules merely to improve a metric.

### Preserve semantic distinctions

Do not collapse different concepts without evidence.

Examples of distinctions that may matter:
- note concept vs ingredient
- same concept vs family
- related scent vs synonym
- raw source field vs derived feature

If a relationship is uncertain, preserve the uncertainty.

### No unsupported scent inference

Do not invent mappings such as an abstract phrase to scent features without a defined evidence or modeling method.

If the task requires semantic inference, make the inference method explicit and keep it separate from source facts.

## External Sources

Do not introduce a new external data source without user approval.

When external evidence is required:
- prefer authoritative or primary sources
- record provenance when the result will become reusable knowledge
- do not treat search snippets or model memory as evidence

## Evaluation Data

Do not change evaluation data because a model disagrees with it.

Potential label issues should be reported separately.

Do not use holdout data for model or rule tuning.

## Code Style for Analysis

Prefer straightforward notebook code.

Avoid creating:
- framework-like analysis infrastructure
- generic pipeline systems
- custom class hierarchies
- configuration systems

unless repeated current usage clearly requires them.

A small local function is preferable to a new module when it is used only in one notebook.

## Audit / Cleanup Tasks

When asked to audit or organize the project:

- inspect only unless modification is explicitly requested
- do not delete, move, rename, merge, or rewrite files during the audit
- classify first, modify later after user approval

Suggested classifications:

### Notebook
- `KEEP`
- `MERGE_CANDIDATE`
- `ARCHIVE`
- `REMOVE_CANDIDATE`

### Output
- `REUSABLE_DATA`
- `NEXT_STEP_INPUT`
- `REPORT_ONLY`
- `INTERMEDIATE`
- `DUPLICATE_CANDIDATE`

## Tabular Analysis Data

CSV files created under `data/` or `analysis_outputs/` are programmatic analysis data,
not formatted spreadsheet deliverables.

For these CSV files:
- use the project's existing Python/Jupyter/pandas stack
- do not add Node.js or spreadsheet-specific dependencies only to write CSV
- use spreadsheet-specific tooling only when the user explicitly requests a formatted spreadsheet artifact such as `.xlsx`

## Completion Rule

Before finishing a task, confirm:

- Did this task answer the requested question?
- Did it reuse existing work where possible?
- Did it create only necessary code and files?
- Is the result understandable without unnecessary abstraction?
- Was the narrowest meaningful verification performed?

If yes, stop. Do not add extra work.
