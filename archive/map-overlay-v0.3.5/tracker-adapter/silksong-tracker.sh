#!/usr/bin/env sh
cd "$(dirname "$0")"
python3 -c 'from PIL import Image' >/dev/null 2>&1 || python3 -m pip install -r requirements.txt || exit 1
python3 -m silksongtracker "$@"
