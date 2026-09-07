# MAP Instructions

## Scope

These instructions apply to work under `MAP/`.
Global Codex instructions still apply; this file only adds MAP-specific context.

## Domain

`MAP` is the perfume-map and supporting data-analysis workspace for the 향해 project.

### Personal Fragrance

Treat products whose primary purpose is to leave a desired scent on the user's body as `Personal Fragrance`.

This can include:
- Parfum / Extrait / EDP / EDT / EDC / Cologne
- oil perfume / roll-on
- hair perfume
- body mist / hair & body fragrance
- solid perfume / perfume balm / perfume cream

### Home Fragrance

Treat products intended primarily for spaces or objects as `Home Fragrance`, such as:
- diffuser
- room spray
- fabric fragrance
- candle
- car fragrance

Keep the two scopes distinct unless the current task explicitly changes the definition.

## Data Integrity

- Raw data is immutable. Do not overwrite or silently clean it.
- HAR files are local snapshots. Use saved contents only; do not make additional network requests unless explicitly requested.
- Preserve source and provenance when available.
- Do not invent missing values or silently repair suspicious values.
- When evidence is insufficient, keep the item unresolved rather than forcing a classification or match.
- Do not merge products only because their names are similar.
- If concentration or product identity differs, keep products separate unless there is explicit evidence to combine them.

## Popularity Signals

Different popularity sources may measure different behavior.

- Sales rankings represent purchase popularity.
- Review/ranking platforms may represent consumer popularity or evaluation.

Do not describe one signal as another unless the source supports that interpretation.

## Measurement

- Report only values produced by actual execution.
- Preserve the previous baseline when rules or methods change, and compare before/after results.
- Distinguish row count, marketplace SKU count, and unique-perfume count.
- Keep failed or inconclusive results when they materially affect a decision.

## Working Principle

Inspect the relevant existing data, scripts, and results before changing the pipeline.
Prefer the simplest approach that reaches the task goal and reuses the current structure.

When changing data-processing logic, rerun the relevant script and report:
- measured results
- validation performed
- unresolved REVIEW / MANUAL_CHECK items
- any limitation that affects the next decision
