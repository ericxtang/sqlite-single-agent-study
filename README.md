# Can one strong coding agent build SQLite in four hours?

A reproducible experiment testing a simple baseline: give **one Astra coding agent** a complex project, four hours and a fixed tool environment, then evaluate the saved implementation independently.

> **Evaluation correction in progress:** [issue #1](https://github.com/ericxtang/sqlite-single-agent-study/issues/1) found Docker launch failures counted as query failures and case-sensitive blob comparisons. Original results below are preserved **v1 measurements, not corrected scores**. [Erratum and regrade status](docs/ERRATUM-001.md).

## Why we ran this experiment

Cursor's [self-driving codebases](https://cursor.com/blog/self-driving-codebases) and [agent-swarm model economics](https://cursor.com/blog/agent-swarm-model-economics) posts demonstrate ambitious software projects built by recursively delegating planner/worker swarms. We wanted a simpler reference point: **how far could a newer, strong coding model get with a single trajectory and a strict four-hour limit?**

This tests the feasibility of that baseline. It is not a controlled test of single-agent versus swarm formation, because we did not run both architectures with the same model and evaluator.

## Most important findings

| Question | What the evidence says |
|---|---|
| Did Astra spawn subagents? | **No.** Subagents and extra inference were disabled. Observable traces show one implementation trajectory per run; ordinary continuation and compaction retained that trajectory. Seven later grading workers were evaluators, not coding agents. |
| How well did it do? | Original completed-run query scores: **96.43–96.74%, median 96.46%, n=3**, after four hours. Exact scores/rankings are under regrade. A fourth attempt was interrupted at about 41 minutes and its terminal source failed to build; it is retained outside the four-hour summary. |
| Is this a complete SQLite replacement? | **No.** The denominator is 5,728,833 eligible query records, not all SQLite behavior. Original secondary totals were 7/12, 8/12 and 10/12; the audit's blob-corrected diagnostics were 10/12, 12/12 and 10/12. Full corrected endpoint results are pending. |
| Did it outperform Cursor's swarms? | **The published headline query percentages are higher, but the comparison is unmatched.** Cursor reported 73–85% for newer swarms at four hours and later 100%. Models, harnesses, exact tests, resource policies and accounting differ. |
| Was it much cheaper? | Recorded usage values at **$70.90–$74.76** under September 21, 2026 Standard API rates and observed cache hits, or **$403.97–$416.68** without cache discounts. These are hypothetical token valuations, not subscription bills or guaranteed reproduction budgets. Cursor's $1,339–$10,565 totals do not establish a matching four-hour/equal-quality cost comparison. |

**Practical takeaway:** try one strong agent as a baseline before adding orchestration. These data motivate that policy; they do not prove swarms are inferior or make Cursor's historical measurements invalid. The next useful test holds the model fixed and compares single-agent and recursive-swarm setups at matched time and spend.

[Full report and original charts](reports/comparison.md) · [Observable trace/strategy review](reports/data/trace-review.json) · [Cost assumptions](reports/data/cost-audit.json) · [Proposed controlled experiment](docs/future-experiments.md)

## How to reproduce or explore the results

Choose the level of reproduction you need. Running a saved artifact and grading it require **no model calls or account**. Running a new implementation requires your own access to the original model and CLI; exact access is not guaranteed.

| Goal | Starting point |
|---|---|
| Read the evidence | [Report](reports/comparison.md), [original result data](reports/data/comparison-data.json), [erratum](docs/ERRATUM-001.md) |
| Try SQL against a saved implementation | Quickstart below; [manual testing guide](docs/manual-testing.md) |
| Regrade unchanged outputs | [Corrected v2 grading guide](docs/grading.md): fetch the pinned corpus and run sequentially |
| Run a fresh four-hour implementation | [Replication guide](docs/replication.md): verify isolation, create a new local seal, explicitly authorize inference |
| Check package integrity without inference | Validation commands below; [validation scope](docs/validation.md) |

### Try a saved implementation

Tested on macOS with Docker Desktop. Linux uses the same Python/Docker workflow but has not been validated end to end. Builds target the original **Linux arm64** environment; x86 hosts need Docker arm64 emulation. Allocate at least 4 CPUs and 6–8 GB to Docker for one worker.

```sh
git clone https://github.com/ericxtang/sqlite-single-agent-study.git
cd sqlite-single-agent-study
python3 replication/manage.py verify
python3 replication/manage.py setup
python3 manual/lab.py console 001
```

At `001>`, enter one statement per line:

```sql
SELECT 2 + 3 AS five;
CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT, qty INTEGER);
INSERT INTO items VALUES (1,'apricot',2),(2,'bread',5);
SELECT name, qty FROM items ORDER BY qty DESC;
BEGIN;
UPDATE items SET qty=99 WHERE id=2;
ROLLBACK;
SELECT qty FROM items WHERE id=2;
.quit
```

Expected: `5`; bread/5 then apricot/2; `5` after rollback. Replace `001` with `002` or `004`. Run `003` intentionally retains its failed terminal build; `003-30min` explicitly selects its earlier diagnostic checkpoint. [Persistence and file-interchange examples](docs/manual-testing.md).

### Repeat the experiment, not just its score calculation

Each completed implementation used `gpt-6-astra`, `xhigh`, a 272k context configuration, four hours, offline Rust tools, 4 CPUs and 4 GiB RAM. The implementing agent received the task, I/O contract and selected documentation. **Do not expose this repository, the saved implementations, hidden corpus or grading feedback to a new implementing agent.** The replication controller provisions only the allowed inputs.

The [replication guide](docs/replication.md) separates setup and isolation checks from the paid inference command. Corpus revision, eligibility filters, normalization, checkpoints and strict stop behavior are specified in the [protocol](PROTOCOL.md) and [scoring rules](SCORING.md). The [v2 erratum](docs/ERRATUM-001.md) records the evaluator correction. Portable wrappers are a new replication harness; they do not recreate every aspect of the original host. [Reproducibility limits](docs/reproducibility.md).

## What to test next

1. **Same model, different formation:** compare Astra alone with a competent Astra planner/worker swarm. Hold task inputs, settings, tools, grading and total machine resources fixed.
2. **Separate time from budget:** compare quality after four hours, then compare quality at the same total spend. Count planners, workers, reviewers, cache categories, unsuccessful billed requests and compute; measure time/cost to the same quality target.
3. **Broaden quality and tasks:** use a private holdout plus file interoperability, recovery, concurrency and performance checks; include other complex projects and longer horizons.
4. **Repeat and preregister:** estimate run/task variance with pilot replications, choose a practical success margin and sample size, randomize run order, retain failures and report uncertainty. Millions of correlated queries do not replace independent runs.

To test whether *newer models reduce the benefit of swarms*, add older/newer model × single/swarm arms. [Detailed design, decision criteria and limitations](docs/future-experiments.md).

## What is in this repository?

- Exact task/continuation prompts and I/O contract; 416 selected SQLite documentation extracts plus index and checksums.
- All **55 measured source checkpoints**, original archive hashes, and **66 retained v1 evaluation attempts covering 59 logical jobs**, including incomplete attempts.
- Frozen v1 scoring code, corrected v2 evaluator, tests, the 622-file corpus manifest and pinned upstream download command.
- Setup, manual consoles, single-agent controller, no-inference isolation checks, local seals and separately versioned grading.
- Report, original charts, reconciled usage aggregates, dated cost scenarios and observable action summaries. Raw private sessions, credentials and platform-provided prompts are excluded.

Source archives and frozen scoring files remain unchanged. Original evidence is permanently available in [v1.0.0](https://github.com/ericxtang/sqlite-single-agent-study/releases/tag/v1.0.0).

## Validate without inference

```sh
python3 -m unittest discover -s evaluator -p 'test_*.py'
python3 -m unittest discover -s replication -p 'test_*.py'
python3 -m unittest discover -s evaluator_v2 -p 'test_*.py'
python3 replication/validate_publication.py
```

CI makes no model calls. Fresh implementation commands require `--allow-inference`; no credentials are included or passed to a worker. [Contributing](CONTRIBUTING.md).

Project code and generated implementations are MIT licensed; SQLite materials and dependencies retain their upstream terms. [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md).
