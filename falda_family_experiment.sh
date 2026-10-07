#!/usr/bin/env bash
# Five-agent deterministic experiment. The original falda_demo.sh remains canonical
# for the short audience demo; this wrapper runs the evidence-producing harness.
set -eu
: "${FALDA_URL:?Set FALDA_URL to the FALDA gateway URL}"
exec python3 "$(dirname "$0")/falda_experiment.py" \
  --gateway "$FALDA_URL" \
  --tenants "${FALDA_FAMILY_TENANTS:-alpha,bravo,charlie,delta,echo}" \
  --pool-prefix "${FALDA_POOL_PREFIX:-falda-family}" \
  --output-dir "${FALDA_RUNS_DIR:-runs}" \
  "$@"
