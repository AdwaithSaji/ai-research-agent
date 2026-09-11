#!/usr/bin/env bash
# Runs the frontend dev server.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
if [ ! -d "node_modules" ]; then
  npm install
fi
npm run dev
