# Regrade saved outputs

Grading makes no model calls. It builds generated source only in isolated Docker containers, sends SQL through the JSON-lines interface, and keeps test files/answers on the controller. Do not mount the repository or corpus into generated-code containers.

```sh
python3 replication/manage.py setup  # once per clone
python3 replication/manage.py fetch-corpus
python3 -m unittest discover -s evaluator -p 'test_*.py'

# Quick diagnostic: first two files, including 45 eligible queries.
python3 replication/grade.py \
  --archive results/measured-001/checkpoints/final.tar.gz \
  --limit-files 2 --output grading/smoke-001

# All four terminal primary + four terminal secondary assessments.
python3 replication/grade.py --preset endpoints --output grading/endpoints --workers 1

# Full 59-job queue: endpoints, secondary assessments and all earlier checkpoints.
python3 replication/grade.py --preset all --output grading/full --workers 7
```

Every output path must be new. Completed or incomplete evaluations are never overwritten or automatically retried. An infrastructure error stops dispatch and signals other active evaluators; inspect the preserved logs, fix infrastructure and create an explicit new retry plan/output. Build failure is a valid zero; infrastructure failure is incomplete, not zero.

Seven concurrent graders each have limits of 4 CPUs/4 GiB, so provide resources accordingly (up to 28 CPUs/28 GiB plus overhead) or expect oversubscription. The original later progress grading used seven workers on a smaller shared Docker host; scheduling and timeout sensitivity are a limitation. Four-hour endpoints originally ran serially. Keep workers=1 for a closer endpoint replay. Full grading can take many hours; the original queue/recovery took 43.56 hours wall time, not 43.56 hours of implementation.

Monitor `grading/full/*.log` and each job's `files.jsonl` as they are written. `plan.json` records the queue; `state.json` records final completion/incompletion. Ctrl-C or SIGTERM the grading controller stops it and signals active evaluators so their cleanup runs. Interrupted summaries and file logs remain available. Verify associated container shutdown with `docker ps --filter name=astra-sqlite-eval-`; do not bulk-remove other workloads.

For a fresh run:

```sh
python3 replication/grade.py --archive runs/replicate-001/checkpoints/final.tar.gz \
  --output grading/replicate-001-primary
python3 replication/grade.py --archive runs/replicate-001/checkpoints/final.tar.gz \
  --suite secondary --output grading/replicate-001-secondary
```

The frozen scorer uses 5,728,833 queries across 622 files. Setup failures taint remaining queries in a file; queries not reached stay in the denominator. Ordinary SELECT mismatches do not taint subsequent queries. The JSON adapter/normalization and dialect filtering are documented in [SCORING.md](../SCORING.md).

**Known secondary limitation:** the frozen secondary suite compares raw typed JSON cells and expects lowercase blob hex, while the I/O contract does not constrain hex case. Uppercase and lowercase can represent identical bytes. Scores retain this original behavior; see the report's seven affected cells and do not treat every such failed cell as proof of incompatible stored data. The primary normalizer decodes hex bytes and is unaffected.

The cleanup adapter in `replication/evaluate.py` wraps the unchanged `evaluator/evaluate_snapshot.py`; it changes process/container cleanup only, following the original reviewed recovery. No query, expected result, denominator, timeout or source artifact is repaired.

## Recompute the published aggregates

This reads the retained 59 logical outputs without executing generated programs or private traces:

```sh
python3 replication/summarize.py --output grading/recomputed-summary
# Optional progress chart:
python3 -m pip install -r requirements-plots.txt
python3 replication/summarize.py --output grading/recomputed-with-plot --plots
```

The exports contain all 55 primary checkpoints, the three completed endpoints, 48 secondary cells, usage categories and historical API valuation arithmetic. The standalone summary deliberately retains the interrupted attempt outside the n=3 endpoint statistics. Full threshold/censoring and regression tables are in the published report/data.
