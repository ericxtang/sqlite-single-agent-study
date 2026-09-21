# Regrade saved outputs

**Use v2 for new grading.** The original evaluator has confirmed scoring defects; see [Erratum 001](ERRATUM-001.md). The historical commands below require an explicit `--legacy-v1` opt-in. They reproduce known-defective scoring and are not corrected evaluations.

## Corrected sequential v2 grading

```sh
python3 replication/manage.py setup
python3 replication/manage.py fetch-corpus
python3 -m unittest discover -s evaluator_v2 -p 'test_*.py'

# Select your locally recorded immutable runtime image ID.
IMAGE_ID=$(python3 -c 'import json; print(json.load(open("records/runtime-image.json"))["id"])')
python3 evaluator_v2/grade.py --preset endpoints --image "$IMAGE_ID" --output grading/v2-endpoints
# All 59 logical jobs, sequentially:
# python3 evaluator_v2/grade.py --preset all --image "$IMAGE_ID" --output grading/v2-all
```

The study correction uses the original image digest recorded in the erratum. A fresh `setup` build can produce a different digest; report that difference. The controller acquires the same lock as fresh implementation runs, verifies the publication/corpus, seals its inputs, and dispatches one job at a time. New output paths are mandatory. `plan.json` and `plan.sha256` identify the inputs; `state.json` contains live controller/evaluator PIDs, completed jobs and current output directory. Each job updates `summary.json` and `files.jsonl`. An infrastructure error stops the queue with no accepted score.

Under each job, `evidence/file-NNNN/` contains `container.json` (launch, runtime and removal evidence), `create.stderr`, `stderr.log` and `protocol.bin.gz`. The lossless protocol format is a concatenation of frames: direction byte (`>` request, `<` response), decimal byte length, a newline, then exactly that many raw bytes. Inspect only outside implementation environments. Preserve all logs, including incomplete attempts. The original source archive is unchanged.

SIGTERM or Ctrl-C the controller to stop it; `records/STOP` is also polled. Verify the associated evaluator exits and `docker ps --filter label=sqlite-evaluator=v2` shows no running v2 containers. Do not remove unrelated workloads. No automatic retries or implementation/model calls occur.

For a small diagnostic before a long queue:

```sh
python3 evaluator_v2/integration_test.py --image "$IMAGE_ID" --output grading/v2-integration
python3 evaluator_v2/evaluate.py --archive results/measured-001/checkpoints/final.tar.gz \
  --limit-files 2 --image "$IMAGE_ID" --output grading/v2-smoke
```

## Historical v1 reproduction (known defects)

Grading makes no model calls. It builds generated source only in isolated Docker containers, sends SQL through the JSON-lines interface, and keeps test files/answers on the controller. Do not mount the repository or corpus into generated-code containers.

```sh
python3 replication/manage.py setup  # once per clone
python3 replication/manage.py fetch-corpus
python3 -m unittest discover -s evaluator -p 'test_*.py'

# Quick diagnostic: first two files, including 45 eligible queries.
python3 replication/grade.py --legacy-v1 \
  --archive results/measured-001/checkpoints/final.tar.gz \
  --limit-files 2 --output grading/smoke-001

# All four terminal primary + four terminal secondary assessments.
python3 replication/grade.py --legacy-v1 --preset endpoints --output grading/endpoints --workers 1

# Full 59-job queue: endpoints, secondary assessments and all earlier checkpoints.
python3 replication/grade.py --legacy-v1 --preset all --output grading/full --workers 7
```

Every output path must be new. Completed or incomplete evaluations are never overwritten or automatically retried. An infrastructure error stops dispatch and signals other active evaluators; inspect the preserved logs, fix infrastructure and create an explicit new retry plan/output. Build failure is a valid zero; infrastructure failure is incomplete, not zero.

Seven concurrent graders each have limits of 4 CPUs/4 GiB, so provide resources accordingly (up to 28 CPUs/28 GiB plus overhead) or expect oversubscription. The original later progress grading used seven workers on a smaller shared Docker host; scheduling and timeout sensitivity are a limitation. Four-hour endpoints originally ran serially. Keep workers=1 for a closer endpoint replay. Full grading can take many hours; the original queue/recovery took 43.56 hours wall time, not 43.56 hours of implementation.

Monitor `grading/full/*.log` and each job's `files.jsonl` as they are written. `plan.json` records the queue; `state.json` records final completion/incompletion. Ctrl-C or SIGTERM the grading controller stops it and signals active evaluators so their cleanup runs. Interrupted summaries and file logs remain available. Verify associated container shutdown with `docker ps --filter name=astra-sqlite-eval-`; do not bulk-remove other workloads.

For a fresh run:

```sh
python3 replication/grade.py --legacy-v1 --archive runs/replicate-001/checkpoints/final.tar.gz \
  --output grading/replicate-001-primary
python3 replication/grade.py --legacy-v1 --archive runs/replicate-001/checkpoints/final.tar.gz \
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
