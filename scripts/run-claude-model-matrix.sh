#!/usr/bin/env bash
set -euo pipefail

models="${ANTHROPIC_MODEL_MATRIX:-claude-opus-4-8 claude-sonnet-5}"
script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
status=0
dry_run=0
post_recheck=1
recheck_latest=0
forward_args=()
recheck_args=()

while (($#)); do
  case "$1" in
    --agent|--agent=*)
      printf '%s\n' "run-claude-model-matrix.sh always uses --agent claude; remove forwarded ${1}" >&2
      exit 2
      ;;
    --dry-run)
      dry_run=1
      forward_args+=("$1")
      shift
      ;;
    --case)
      if (($# < 2)); then
        printf '%s\n' "run-claude-model-matrix.sh: --case requires a value" >&2
        exit 2
      fi
      forward_args+=("$1" "$2")
      recheck_args+=("$1" "$2")
      shift 2
      ;;
    --case=*)
      forward_args+=("$1")
      recheck_args+=("$1")
      shift
      ;;
    --no-post-recheck)
      post_recheck=0
      shift
      ;;
    --recheck-latest|--recheck-only)
      recheck_latest=1
      post_recheck=0
      shift
      ;;
    *)
      forward_args+=("$1")
      shift
      ;;
  esac
done

for model in $models; do
  if ((recheck_latest)); then
    printf '%s\n' "==> Recheck latest Claude blindbox artifacts: ${model}"
    if ! python3 "$script_dir/okr-runner.py" recheck-blindbox --latest --agent claude --model "$model" "${recheck_args[@]}"; then
      status=1
    fi
    continue
  fi

  printf '%s\n' "==> Claude blindbox model: ${model}"
  if ! ANTHROPIC_MODEL="$model" "$script_dir/run-blindbox.sh" "${forward_args[@]}" --agent claude; then
    status=1
  fi
  if ((post_recheck)) && ((! dry_run)); then
    printf '%s\n' "==> Current-check preserved artifact: ${model}"
    if ! python3 "$script_dir/okr-runner.py" recheck-blindbox --latest --agent claude --model "$model" "${recheck_args[@]}"; then
      status=1
    fi
  fi
done

exit "$status"
