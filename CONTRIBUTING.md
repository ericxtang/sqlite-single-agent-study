# Contributing

Changes to portability, documentation and analysis are welcome. Preserve the original checkpoint archives and scoring behavior. New experiment results belong in a separately identified dataset, with all attempts and deviations recorded; do not replace the historical measurements.

Run the no-inference tests in the README. If changing scoring, document a new protocol/version and publish both original and revised outcomes. Do not silently normalize the known secondary blob-case issue in a historical score.

When changing public files, intentionally regenerate `publication-manifest.json` from the reviewed Git allowlist before committing. Exclude that manifest itself, all ignored local state and `.git`. Never regenerate an existing local experiment seal after inference. A new replication protocol needs a new clone/seal.

Do not submit auth files, complete private sessions/platform prompts, personal automation state, or private reasoning transcripts. Prefer aggregate usage, observable action summaries, code artifacts and explicit validation evidence. Open an issue describing your environment and sanitized error when setup cannot reproduce the documented behavior.
