#!/bin/sh
set -eu

exec marimo edit \
  --host 0.0.0.0 \
  --port 2718 \
  --headless \
  --no-token
