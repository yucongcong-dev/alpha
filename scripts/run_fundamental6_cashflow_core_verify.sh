#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
RUN_DATE="${RUN_DATE:-$(date +%F)}"
OUTPUT_BASENAME="${OUTPUT_BASENAME:-verify_cashflow_core_${RUN_DATE}.json}"
LIMIT="${LIMIT:-1}"
MAX_TEMPLATES_PER_FIELD="${MAX_TEMPLATES_PER_FIELD:-5}"
MAX_TEMPLATES_PER_FAMILY="${MAX_TEMPLATES_PER_FAMILY:-2}"
FIELD_TEMPLATE_BATCH_SIZE="${FIELD_TEMPLATE_BATCH_SIZE:-1}"
STOP_AFTER_SUBMITTABLE="${STOP_AFTER_SUBMITTABLE:-1}"

cd "${ROOT_DIR}"

exec "${PYTHON_BIN}" -m alpha \
  --dataset-id fundamental6 \
  --template-library-file templates/fundamental6/refine/cashflow_submit_core_pack.json \
  --include-fields-file templates/fundamental6/refine/fields/cashflow_submit_core_field.txt \
  --include-templates-file templates/fundamental6/refine/templates/cashflow_submit_core_templates.txt \
  --limit "${LIMIT}" \
  --max-templates-per-field "${MAX_TEMPLATES_PER_FIELD}" \
  --max-templates-per-family "${MAX_TEMPLATES_PER_FAMILY}" \
  --field-template-batch-size "${FIELD_TEMPLATE_BATCH_SIZE}" \
  --stop-after-submittable "${STOP_AFTER_SUBMITTABLE}" \
  --no-auto-update-blacklist \
  --output "results/fundamental6/${OUTPUT_BASENAME}" \
  --feedback-output "results/fundamental6/${OUTPUT_BASENAME}" \
  "$@"
