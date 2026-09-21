# Test the hypothesis: start with one strong coding agent

## What this study supports

A strong single coding agent is a credible, comparatively simple **baseline to try first** for a bounded project. This study produced three high query-suite results from four-hour Astra trajectories with no delegated agents. It motivates testing whether coordination is worth its cost. It does not show that single agents generally outperform swarms, nor does it invalidate Cursor's historical measurements.

Astra's original 96.43–96.74% and Cursor's reported 73–85% four-hour range were measured with different models, harnesses and incompletely matched test methods. Our exact scores are also under [evaluation correction](ERRATUM-001.md). “Over 95% of eligible queries” is not “95% of SQLite”: correlated records, uneven feature coverage, file compatibility, crashes, concurrency and performance matter. Cursor's new configurations later reached 100% of their suite; our four-hour artifacts did not complete our suite.

The original cost scenarios are not matched bills. Our $70.90–$74.76 values subscription token telemetry at dated Standard API prices with 95–97% input cache hits. Without cache discounts the same tokens value at $403.97–$416.68. Cursor's $1,339–$10,565 configuration totals have a different, insufficiently specified accounting horizon. Neither an equal-quality savings ratio nor a swarm coordination overhead can be inferred by dividing those numbers.

Sources: [Cursor's February architecture post](https://cursor.com/blog/self-driving-codebases), [July model economics post](https://cursor.com/blog/agent-swarm-model-economics), [study report](../reports/comparison.md), [cost assumptions](../reports/data/cost-audit.json).

## First controlled comparison

Hold the model fixed to Astra and vary orchestration. Use the same task instructions, tool/document access, model settings, grading contract, resource policy and hidden holdout. Give each architecture a competent, frozen harness validated on separate pilot tasks before measurement; a deliberately weak swarm would answer the wrong question.

| Arm | Formation | Question |
|---|---|---|
| A: single agent | One trajectory plans, codes, tests and reviews; normal continuation/compaction | Baseline |
| B: recursive swarm | Root planner can delegate to planners/workers, with ownership, handoffs and integration; fixed maximum concurrency | Does delegation add value with the same model? |
| C: optional hybrid | Same topology, strongest planner plus cheaper workers | Does a mixed-model policy improve the cost/quality frontier? This changes more than formation. |

Start with A versus B. Choose and preregister the swarm cap (for example, four workers) and whether planner/reviewer slots count toward it. Keep the total CPU/RAM allocation equal for the causal formation comparison. A second practical deployment comparison can grant additional resources to the swarm and count their cost explicitly. Do not confuse seven post-hoc grading processes with seven implementation agents.

## Two separate budget questions

1. **Same deadline:** after four hours, which approach produces better independently graded software, and how much did each cost? Count thinking, compilation, testing, coordination, compaction and handoffs within the clock. Report all attempts, including failures.
2. **Same total spend:** with the same dollar cap, which approach produces better software, or reaches a preregistered quality target sooner? Include every planner, worker, reviewer, cached-read/write and output charge, unsuccessful/in-flight requests where billed, and host compute. Stop at the budget; do not retrospectively choose the winning checkpoint.

Report cost and time to agreed quality levels as well as fixed-budget quality. Use 95%, 99% and 100% thresholds only for the specified test suite, with additional compatibility gates if those are product requirements. Treat unmet thresholds as censored. Full completion may reverse a ranking seen at four hours.

## Measurement and replication

- Complete the evaluator correction first, then freeze the new grader and use it for every arm. Validate it against reference SQLite and deliberate bad implementations. Run evaluation with matched resources and avoid oversubscribed timeout-sensitive workers.
- Obtain Cursor's exact corpus revision, filters, comparator, timeouts, workload weighting, agent counts and cost windows if possible. Without them, treat the blog comparison as context, not a head-to-head replication.
- Add a new private holdout, differential/property-based SQL cases, persistence/file interchange, crash recovery, concurrency, performance and manual code review. Freeze scoring before runs. Avoid tuning agents on the published benchmark or leaking test feedback between trajectories.
- Use multiple independent runs per task and several complex projects, including longer horizons and tasks that naturally divide into modules. Five to ten runs per arm can be a variance-estimation pilot; select confirmatory sample sizes from the observed variance and a preregistered practical effect, not that rule of thumb.
- Randomize/block run order by task and platform conditions. Report uncertainty over **runs/tasks**, not millions of correlated queries. Pair comparisons by task, retain failed/interrupted attempts, and define exclusions/replacements in advance.
- Preregister the primary outcome and a useful decision margin. For example, test whether the simpler single-agent setup is within one percentage point on the frozen query metric **and** passes the same required compatibility gates, then compare cost. That example margin is a decision choice, not established by these data.

For the stronger “new models make swarms unnecessary” claim, add a **model generation × formation** comparison: older/newer model, each in single and recursive-swarm modes, with matched settings and access where available. A model-by-formation interaction would test whether delegation's value changes as model capability improves. A single newer-model-versus-older-swarm comparison cannot separate those effects.

## Practical decision today

Start with the strongest suitable single agent as the baseline; instrument cost, elapsed time and correctness. Introduce delegation when the baseline hits observed limits, then demand a measured benefit on the same task and budget. This is a testable operating policy, not a universal claim that swarms are inferior. No new inference experiment has been launched as part of this proposal.
