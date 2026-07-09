# Hybrid Token-Efficient Routing Agent

AMD Developer Hackathon — Act II — Track 1 (General-Purpose AI Agent)

See `PROJECT_SPEC.md` for full architecture, rules/constraints, and diagrams.
This README covers only how to run and test the code.

## What this container does

Reads `/input/tasks.json`, classifies each prompt into one of 8 capability
categories using zero-token rule-based logic, routes each to the cheapest
Fireworks model likely to answer it correctly, validates the answer with
cheap rule-based checks, escalates to a pricier model only on failure, and
writes `/output/results.json`. No server, no frontend, no dashboard — a
single batch run that exits.

## Project layout

```
main.py                    entrypoint — orchestration, deadline, exit codes
src/
  task_loader.py           read + validate /input/tasks.json
  category_classifier.py   zero-token rule-based classification (8 categories)
  tier_policy.py           resolves ALLOWED_MODELS into cost-ordered tiers
  fireworks_client.py      all Fireworks API calls go through here
  answer_validator.py      cheap rule-based per-category validation
  escalation_controller.py per-task classify -> call -> validate -> escalate
  concurrency_manager.py   bounded-parallel execution across all tasks
  result_writer.py         schema-validated /output/results.json writer
config/
  tier_mapping.yaml        category -> starting tier + max escalations
tests/                     offline unit + integration tests (no network)
dev/                       local-only eval helper, excluded from the image
```

## Running tests locally (no Fireworks credentials needed)

```bash
pip install -r requirements.txt
python3 tests/test_category_classifier.py
python3 tests/test_answer_validator.py
python3 tests/test_task_loader.py
python3 tests/test_integration_smoke.py
```

All four should print a "passed" line with no traceback.

## Offline routing sanity check

```bash
python3 dev/local_eval.py dev/sample_tasks.json
```

Prints, for each sample prompt, which category it was classified into and
which model tier sequence it would use — useful for eyeballing routing
decisions before spending real tokens.

## Building the image

**Important — platform requirement:** the judging infrastructure pulls and
runs `linux/amd64` images. If you're building on an ARM machine (Apple
Silicon M1/M2/M3), a plain `docker build` produces an arm64 image, which
will pass locally but fail with `PULL_ERROR` on submission. Always build
with an explicit platform flag:

```bash
docker buildx build --platform linux/amd64 -t routing-agent:latest .
```

On an already-Intel/AMD machine this is harmless to include as well — safe
to use unconditionally.

## Troubleshooting a failed submission

The hackathon harness reports one of these statuses if something goes
wrong. Check container logs locally (`docker run` output) to reproduce
before resubmitting — submissions are rate-limited to 10/hour.

| Status | Meaning | Where to look in this codebase |
|---|---|---|
| `PULL_ERROR` | Image couldn't be pulled — usually a missing `linux/amd64` manifest | Rebuild with `docker buildx build --platform linux/amd64` (see above) |
| `RUNTIME_ERROR` | Container exited non-zero | Check logs for a traceback; `main.py`'s top-level try/except should catch and log this — if you see a raw traceback instead, something bypassed it |
| `TIMEOUT` | Didn't finish in 10 minutes | Check `EFFECTIVE_DEADLINE_SECONDS` in `main.py`, confirm `concurrency_manager.py` is respecting `deadline` and not retrying forever |
| `OUTPUT_MISSING` | Exited cleanly but never wrote `/output/results.json` | Confirm `RESULTS_OUTPUT_PATH`/`OUTPUT_PATH` actually resolves to `/output/results.json` inside the container (not a local dev override left in place) |
| `INVALID_RESULTS_SCHEMA` | Output JSON malformed or missing `task_id`/`answer` | `result_writer.py` validates this — if you see this status, something wrote to the output path *outside* `write_results()` |
| `MODEL_VIOLATION` | Called a model not in `ALLOWED_MODELS` | Confirm you're not caching an old hardcoded model string anywhere; `tier_policy.py` should be the only source of model IDs, always read from env at runtime |
| `IMAGE_TOO_LARGE` | Image over 10GB compressed | Check `.dockerignore` is being respected; confirm no local model weights or dev/test assets leaked into the image (`docker images` to check size) |
| `ACCURACY_GATE_FAILED` | Ran fine, but answers scored below threshold | Not an infra bug — tune `answer_validator.py` strictness and `tier_mapping.yaml` start tiers per category (see local eval workflow below) |
| `ZERO_API_CALLS` (flag, not a failure) | Made zero calls through the Fireworks proxy | Only relevant if you intentionally go local-model-only; if you see this unexpectedly, it likely means every call failed before reaching Fireworks (check `FIREWORKS_BASE_URL`/model IDs) or the input file was empty |

**Note on token counting:** the task prompts are identical for every team —
your token count is driven by your system prompt (currently none, kept
deliberately minimal) and your model's response length
(`max_tokens: 600` in `config/tier_mapping.yaml`). Don't tune output
length until routing accuracy is solid — that's a later-stage optimization,
not a first pass.

## Running locally against real Fireworks credentials (dev only)

```bash
cp .env.example .env   # fill in your own dev key — never commit this file
export $(grep -v '^#' .env | xargs)
mkdir -p /tmp/input /tmp/output
cp dev/sample_tasks.json /tmp/input/tasks.json
docker run --rm \
  -e FIREWORKS_API_KEY \
  -e FIREWORKS_BASE_URL \
  -e ALLOWED_MODELS \
  -v /tmp/input:/input \
  -v /tmp/output:/output \
  routing-agent:latest
cat /tmp/output/results.json
```

## Submission

Push the built image to a public registry (GHCR / Docker Hub) per the
hackathon's submission instructions. Nothing in `dev/` or `tests/` ships in
the image — see `.dockerignore`.
