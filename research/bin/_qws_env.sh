# _qws_env.sh — source this at the top of every research/bin/ runner.
# Sets up repo root, loads .env, cds to repo root, and defines record_artifact.
#
# Usage in caller:
#   source "${0:A:h}/_qws_env.sh"

_QWS_ROOT="$(git -C "${0:A:h}" rev-parse --show-toplevel 2>/dev/null || echo "${0:A:h:h:h}")"
_QWS_ENV_FILE="$_QWS_ROOT/qws_graph/.env"
if [[ -f "$_QWS_ENV_FILE" ]]; then
  set -o allexport
  source "$_QWS_ENV_FILE"
  set +o allexport
fi
unset _QWS_ENV_FILE
cd "$_QWS_ROOT"
unset _QWS_ROOT

record_artifact() {
  local artifact_file="$1"
  local artifact_kind="$2"
  local source_file="${3:-}"

  # Python writes may still be buffered when the process exits.
  sleep 1

  if [[ ! -f "$artifact_file" ]]; then
    echo "WARNING: expected artifact not found: $artifact_file" >&2
    return
  fi

  local source_flag=()
  if [[ -n "$source_file" ]]; then
    source_flag=(--source-file "$source_file")
  fi

  if [[ "${QW_GRAPH_ENABLED:-true}" == "false" ]]; then
    qw record --file "$artifact_file" --kind "$artifact_kind" "${source_flag[@]}" --offline || true
    return
  fi

  qw record --file "$artifact_file" --kind "$artifact_kind" "${source_flag[@]}" || true
}
