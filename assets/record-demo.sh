#!/bin/bash
# Apte demo script - typed-out commands for asciinema recording.
# Run from the directory containing demo_session.py. Regenerate the cast with:
#   uvx asciinema rec --cols 100 --rows 34 --overwrite -c "bash demo.sh" demo.cast

set -e
cd "$(dirname "$0")"

PROMPT=$'\033[1;32mapte-demo\033[0m \033[1;34m❯\033[0m '
RESET=$'\033[0m'
DIM=$'\033[2m'

# Type a string out character by character, like a human at the keyboard.
type_cmd() {
  local s="$1"
  printf '%s' "$PROMPT"
  for ((i = 0; i < ${#s}; i++)); do
    printf '%s' "${s:i:1}"
    sleep 0.028
  done
  printf '\n'
  sleep 0.35
}

# A typed-out comment line (no execution).
type_note() {
  printf '%s' "$PROMPT"
  printf '%s' "$DIM"
  local s="$1"
  for ((i = 0; i < ${#s}; i++)); do
    printf '%s' "${s:i:1}"
    sleep 0.02
  done
  printf '%s\n' "$RESET"
  sleep 0.6
}

sleep 0.8
type_note "# Tests and LLM evals, one async framework. -n 4 runs them in parallel."
sleep 0.5

# 1. Tests - fixtures + tests await real I/O; watch results stagger in.
type_cmd "apte run demo_session:tests -n 4"
apte run demo_session:tests -n 4 || true
sleep 1.4

# 2. Evals - an eval is a test that returns a value, scored not asserted.
type_cmd "apte eval demo_session:evals -n 4"
apte eval demo_session:evals -n 4 || true
sleep 2.5
