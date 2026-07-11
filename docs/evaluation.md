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
