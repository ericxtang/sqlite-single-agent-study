# Erratum 001: evaluator launch failures and blob comparison

**Status: fixes implemented; full sequential terminal regrade running (results pending).** September 21, 2026. Tracks [issue #1](https://github.com/ericxtang/sqlite-single-agent-study/issues/1). The original [v1.0.0 release](https://github.com/ericxtang/sqlite-single-agent-study/releases/tag/v1.0.0), `evaluator/`, source archives, original grades and incomplete attempts remain unchanged. Corrected evaluation uses `evaluator_v2/` and separate output directories. No implementation agent is resumed and no generated source is repaired.

## What was wrong

1. **Launch failure could become a valid zero.** The v1 protocol client discarded stderr. A failed Docker launch closed stdout, and the scorer treated this like a crashed implementation, failing the remaining queries in that file. A real name collision reproduced this error. Infrastructure errors should instead leave the evaluation incomplete with no accepted numerical score.
2. **Secondary blob comparison was case-sensitive.** The I/O contract allows even-length hexadecimal blob values without imposing letter case. `00ff` and `00FF` contain the same bytes. The frozen secondary checker compared their JSON spelling and rejected valid uppercase results. The primary query normalizer already decoded blob bytes; this second defect affects secondary probes.

The independent audit reports original → blob-normalized diagnostic outcomes of **001: 7→10/12; 002: 8→12/12; 004: 10→10/12**. Our v2 smoke assessment independently reproduced 001 at **10/12**; see [validation evidence](../reports/data/v2-validation.json). These targeted diagnostic results are not the new official endpoint regrade. In particular, do not repeat the original conclusion that only one implementation supports the reference-file read probe: the audit recovered that case for 002. Twelve successful probes would still not establish comprehensive SQLite compatibility.

## What remains uncertain

We independently reproduced the launch and blob defects and the audit's screen of the saved logs:

| Original endpoint | Suspicious file records | Queries in flagged files | Share of denominator |
|---|---:|---:|---:|
| 001 | 7 | 53,695 | 0.9373 percentage points |
| 002 | 5 | 40,372 | 0.7047 percentage points |
| 004 | 7 | 63,343 | 1.1057 percentage points |

Screen: closed input/stdout, zero queries and statements passed, and less than 0.05 seconds of scoring. Across successful-build primary results, **86 records in 16 of 46 evaluations** match. [Complete screen data](../reports/data/v1-launch-audit.json).

Historical launch evidence was not retained. The screen cannot prove the cause of each failure or recover its counterfactual score. **Do not add these queries to the original pass counts.** Exact endpoint rankings, apparent progress regressions and threshold intervals remain provisional. Unsuspicious logs are not proof that no infrastructure error occurred.

## Correction and acceptance

The v2 evaluator:

- Creates a uniquely named container per file/process, records the owned container ID, then separately starts/attaches and confirms launch through Docker inspection. It never removes a pre-existing container after a name collision.
- Records creation stderr/status, protocol stderr, launcher exit codes, relevant container states and verified removal. Failed runtime control or unconfirmed launch raises an infrastructure exception outside the frozen scorer's failure handlers.
- Preserves genuine generated-program errors, crashes, request/file deadlines, resource exhaustion and compiler failures as implementation outcomes. A generated process can legitimately exit 125; exit code alone is not the classifier.
- Captures exact request/response bytes in compressed, length-delimited files, including invalid responses. Hidden corpus files and expected answers remain on the controller.
- Changes the secondary comparison only for blob spelling: valid hex is decoded and compared by bytes. Type tags, row shape and all other comparisons retain their original semantics; malformed hex is rejected.
- Retains the original primary parser, filters, expected results, normalizer and denominator. Limits remain 4 CPUs/4 GiB, 300 seconds to build, 300 seconds per primary file, 10 seconds per request, 16 MiB per response, and 180 seconds per secondary process. Logging/launch verification add evaluation overhead; this is a versioned correction, not a bit-identical harness replay.

No-inference regression tests cover equivalent/malformed/unequal blobs, all twelve reference probes, infrastructure exceptions bypassing the scorer, incomplete summaries, an actual Docker name collision, an actual generated-process exit 125, a request timeout, raw capture and cleanup. The frozen 25 tests are retained as well.

The full terminal regrade launched at **2026-09-21 18:34 UTC** and runs **one worker**, using unchanged 001/002/004 four-hour archives, the interrupted 003 terminal artifact, and the original immutable arm64 image `sha256:c379c6128e193682c40015eb8b126e2916b18c3985f0fb72cf1c642a1a3039f5`. The four primary and four secondary results will be published beside v1. Every retry, if required, needs a recorded new attempt; incomplete evidence is never overwritten. Primary results are not corrected until their entire corpus and cleanup complete.

**Progress regrading:** the screen affects 16 evaluations, not just endpoints. To publish corrected progress curves, regressions or threshold intervals, regrade all earlier saved checkpoints under v2 rather than selecting only suspicious records. Until that follow-up is complete, the 55-point v1 curves remain explicitly historical and uncorrected. Terminal regrading alone cannot validate them.

## Reproduce the correction

See [v2 grading instructions](grading.md). Source archives and all v1 result checksums still validate using `python3 replication/validate_publication.py`. New local output paths, sealed plans and raw logs are kept separate from published original results. Raw protocol logs contain the benchmark SQL and must never be made visible to an implementing agent.

## Controller review follow-up

[PR review 4065296060](https://github.com/ericxtang/sqlite-single-agent-study/pull/2#discussion_r4065296060) identified that atomic queue-state replacement did not explicitly sync the file and directory. The corrected controller syncs both and closes the directory descriptor even on error. Four targeted tests cover ordering, failure behavior and a real filesystem write. This affects recovery metadata after abrupt host failure, not scoring semantics. The active terminal queue remains on its original sealed controller at commit `a4386b4`; its live source files are unchanged. The patch was developed in a separate checkout for subsequent invocations. Existing output, timestamps and evidence are preserved; this finding does not require rerunning the current evaluation.
