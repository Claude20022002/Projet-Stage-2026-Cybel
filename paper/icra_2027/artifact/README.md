# Reclaiming Closed Service Robots — artifacts

Supporting material for the ICRA 2027 submission *Reclaiming Closed Service Robots: A
Hypothesis-Driven Methodology for Non-Destructive Protocol Reconstruction*.

Anonymised for double-blind review. The institution, the city, the robot model and the vendor
application names are replaced by neutral placeholders throughout; nothing else is altered.

---

## What is here, and what it backs

| Path | Backs |
|---|---|
| `sdk/constants.py` | The recovered command surface: topics, services, status codes, gates |
| `scripts/collect_paper_data.py` | Every measurement campaign (Sections IV-C, VI) |
| `scripts/test_poi_nav.py` | The single-shot navigation check that exposed the malformed call |
| `scripts/introspect.py` | Service and topic introspection |
| `scripts/measure_faq_repeat_rate.py` | The 27/48 question-matching result |
| `scripts/measure_voice_latency.py` | Interaction-loop latency and wake events |
| `tools/stats.py` | Every interval and test quoted in the paper |
| `data/paper_metrics.json` | Protocol inventory, teleoperation, bench comparison, tours |
| `data/logs/tour/*.log` | 34 instrumented guided tours |
| `data/logs/voice/*.log` | Interaction-loop timings and wake events |
| `data/navigation_events.json` | The 17 field commands behind H4 |
| `data/faq_repeat_rate.json` | Per-trial question-matching outcomes |
| `data/knowledge_base.json`, `points.json`, `lab_tour.json` | Deployment configuration |

Nothing is included that no claim in the paper rests on.

---

## Reproducing without a robot

```bash
python tools/stats.py                      # every interval and test in the paper
python scripts/measure_voice_latency.py    # latency by exchange kind, wake events
PYTHONPATH=. python scripts/measure_faq_repeat_rate.py   # recomputes 27/48
```

`tools/stats.py` is the authority: the tables and the figures must agree with it. If you change a
count, rerun it rather than editing an interval by hand.

Requires Python 3.11+. Only `scripts/collect_paper_data.py` and `scripts/test_poi_nav.py` need
`websockets`, and only when a robot is present.

## Reproducing with a robot

These talk to a live chassis over the WebSocket bridge and will move it.

```bash
python scripts/introspect.py --host <chassis-ip>
python scripts/test_poi_nav.py --host <chassis-ip> --dry-run    # verifies, does not move
python scripts/test_poi_nav.py --host <chassis-ip>              # moves the robot
python scripts/collect_paper_data.py --host <chassis-ip> --phase nav --nav-trials 10
```

Run `--dry-run` first. It checks the service signature and the target annotation without issuing
a motion command, which is exactly the step whose absence invalidated two earlier campaigns.

---

## Reading the logs

Both log directories are JSON Lines, one event per line.

`data/logs/tour/` — one file per guided tour. `tour_start` carries the stop list and how each
stop is addressed; `nav_result` records the outcome of each leg; `tour_end` carries the final
state. Note that `stopped` means an operator ended the session, not that anything failed: the
distinction matters for the counts in Section VI-D and cannot be recovered from summary files.

`data/logs/voice/` — `voice_exchange` records one interaction with its `kind` and `latency_ms`;
`wake_trigger` records a wake-phrase detection and whether a command followed. Latency must be
read per `kind`: exchanges that only look up an answer and exchanges that also move the robot
differ by more than an order of magnitude, and pooling them produces a figure that describes
neither.

A few `latency_ms` values are negative, from clock skew between the recognition app and the
backend. They are left in the raw logs and excluded from the analysis; see the paper's
Limitations.

---

## Anonymisation

Applied to file contents, not only to the repository name:

| Replaced | By |
|---|---|
| Institution name | `INSTITUT` |
| City | `METROPOLE` |
| Country | `PAYS` |
| Vendor deployment application | `DeploymentTool` |
| Vendor welcome application | `WelcomeApp` |

Substitutions are consistent, so keyword-matching structure is preserved and the 27/48 result
recomputes unchanged. This repository has no commit history from the working repository.

Private network addresses (`10.42.0.x`, `172.16.0.x`, `192.168.20.x`) are kept: they are part of
the recovered topology described in Section III and identify no one.
