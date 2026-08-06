#!/bin/bash

PYTHON_BIN="/var/apps/python312/target/bin/python3"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/cgi_proxy.py"
