# Session 06 CAG stress report

This report is generated from `evals/stress/results.csv`. The committed CSV is a deterministic full stress baseline with 900 data rows. It measures the instrumentation, runner, metric wiring, memory drift behavior, token growth, cost shape, and reporting contract of the existing CAG system. It does not optimize prompts, memory limits, provider strategy, attachment limits, or implement RAG.

## Summary table

| scenario | rows | p50 latency ms | p95 latency ms | accumulated cost usd | exact hit rate | semantic hit rate | fact recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| contradiction | 300 | 0.0 | 0.0 | 0.056284 | 0.00% | 0.00% | 15.00% |
| growing | 300 | 0.0 | 2.0 | 0.057209 | 0.00% | 0.00% | 0.00% |
| pivot | 300 | 0.0 | 0.0 | 0.056351 | 0.00% | 0.00% | 0.00% |

## Curve 1: latency vs tokens

| tokens_in bucket | rows | p50 latency ms | p95 latency ms |
| --- | --- | --- | --- |
| 0-999 | 99 | 0.0 | 0.0 |
| 1000-1999 | 144 | 0.0 | 12.0 |
| 2000-2999 | 657 | 0.0 | 1.0 |

## Curve 2: cumulative cost vs turn

| turn | average turn cost usd | cumulative average cost usd |
| --- | --- | --- |
| 1 | 0.00016571 | 0.00016571 |
| 2 | 0.00008994 | 0.00025564 |
| 3 | 0.00011455 | 0.00037020 |
| 4 | 0.00013891 | 0.00050911 |
| 5 | 0.00016339 | 0.00067250 |
| 6 | 0.00018786 | 0.00086036 |
| 7 | 0.00021225 | 0.00107261 |
| 8 | 0.00020972 | 0.00128233 |
| 9 | 0.00020921 | 0.00149154 |
| 10 | 0.00020897 | 0.00170051 |
| 11 | 0.00020869 | 0.00190921 |
| 12 | 0.00020816 | 0.00211736 |
| 13 | 0.00020795 | 0.00232531 |
| 14 | 0.00020755 | 0.00253286 |
| 15 | 0.00020720 | 0.00274006 |
| 16 | 0.00020683 | 0.00294689 |
| 17 | 0.00020680 | 0.00315369 |
| 18 | 0.00020673 | 0.00336042 |
| 19 | 0.00020678 | 0.00356720 |
| 20 | 0.00020711 | 0.00377431 |

## Curve 3: recall vs N

| N | rows | fact recall |
| --- | --- | --- |
| 1 | 45 | 0.00% |
| 3 | 45 | 0.00% |
| 6 | 45 | 0.00% |
| 10 | 45 | 0.00% |
| 20 | 45 | 33.33% |

## Reading

The most important quantitative claim in this deterministic run is: from turn N=3, fact recall falls below 60%. Another cost claim is: turn 20 average cost is 1.25 times turn 1 average cost. These claims are intentionally mechanical and reproducible from the CSV, so they can be challenged directly during the live review.

Latency should be read together with `tokens_in` and `attachments_total_chars`, not in isolation. In this committed deterministic run, many latency values are near zero because the provider path is intentionally local and fake. The useful signal is therefore the shape of the observation contract, token growth, cost accounting, and recall drift. For a live provider run, this same curve becomes the early warning line for the moment where CAG stops being cheap enough and RAG becomes architecturally attractive.


## Live provider smoke cross-check

A bounded live provider smoke was also run locally with DeepSeek to confirm that the same HTTP runner works against the real provider path without launching 900 live LLM calls.

| scope | rows | scenarios | attachment sizes | repeats | turns | provider signal |
| --- | ---: | --- | --- | ---: | ---: | --- |
| live smoke | 90 | growing, pivot, contradiction | 0, 5, 20, 50, 100 KB | 3 | 2 | DeepSeek flash |

Observed live-smoke summary:

| scenario | rows | p50 latency ms | p95 latency ms | accumulated cost usd | exact hit rate | semantic hit rate | fact recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| contradiction | 30 | 32.5 | 12047.0 | 0.053943 | 66.67% | 0.00% | 0.00% |
| growing | 30 | 14.5 | 12010.0 | 0.055914 | 86.67% | 0.00% | 0.00% |
| pivot | 30 | 47.0 | 13570.0 | 0.067692 | 66.67% | 0.00% | 0.00% |

This live smoke is not the committed full matrix. It is a sanity check proving that the same runner and observation contract work with real provider latency, token, and cost metadata.

## Limitations

The committed 900 row report was produced with deterministic stress mode, so token, cost, and latency numbers should be read as reproducible stress smoke values, not live provider economics. A bounded live provider smoke was also validated locally with DeepSeek using 90 rows: 3 scenarios, 5 attachment sizes, 3 repeats, and 2 turns. That live smoke confirmed the real provider path without running 900 live LLM calls. This report should be used as a coursework CAG baseline, not as a production benchmark.
