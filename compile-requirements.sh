#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

if command -v uvx >/dev/null 2>&1; then
    COMPILER=(uvx --python 3.10 --from pip-tools --with "pip<26" --with typing-extensions pip-compile)
elif command -v pip-compile >/dev/null 2>&1; then
    COMPILER=(pip-compile)
else
    echo "pip-tools is required. Install it with: python3.10 -m pip install pip-tools" >&2
    exit 1
fi

CUSTOM_COMPILE_COMMAND="./compile-requirements.sh" "${COMPILER[@]}" \
    --resolver=backtracking \
    --strip-extras \
    --output-file=images/restapi/requirements.txt \
    images/restapi/requirements.in

CUSTOM_COMPILE_COMMAND="./compile-requirements.sh" "${COMPILER[@]}" \
    --resolver=backtracking \
    --strip-extras \
    --output-file=src/www/requirements.txt \
    src/www/requirements.in
