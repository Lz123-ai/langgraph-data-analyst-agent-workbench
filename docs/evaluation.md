# Layered Agent Evaluation

The project does not treat a fixed intent suite as proof of general intelligence.

| Layer | Primary assertions |
| --- | --- |
| Intent | goal, metrics, dimensions, filters, time scope |
| Plan | operation type, path, aggregation, template |
| Execution | numeric tolerance, ordering, key rows, scope |
| Grounding | insights reference actual tables and methods |
| Safety | path/SQL boundaries, injection, destructive requests |
| Robustness | paraphrases, mixed language, unsupported prediction and causality |
| Runtime | replay, multiple readers, cancellation, restart auto-rerun |
| UI | upload, SSE completion, chart/result/report rendering, errors |

A failure should first become a regression case, then be fixed in the parser, plan validator, tool, or report layer. Provider-enabled and rule-only runs are reported separately because their cost, latency, and failure modes differ.
## Public CI and private enterprise data

## Public CI

The repository always runs unit tests, coverage, the public batch evaluation,
frontend tests, E2E, and Docker build validation. The enterprise business
evaluation intentionally uses a separately distributed dataset and is skipped
in a clean public GitHub Actions runner when that fixture is unavailable.

## Enterprise evaluation

Run the enterprise suite locally after receiving the dataset through an
approved private channel:

```powershell
.\.venv\Scripts\python.exe agent_eval\enterprise_business_eval.py --data-dir <dataset-directory>
```

The command fails when an explicitly supplied dataset is incomplete. Do not add
private business CSV files or benchmarks to the public repository.
