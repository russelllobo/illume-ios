#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mirror_dir="$HOME/.local/share/iphone-mirror"

if [[ ! -f "$mirror_dir/mirror.py" || ! -f "$mirror_dir/cli.py" ]]; then
  echo 'Install the desktop iphone-mirror service first.' >&2
  exit 1
fi

if grep -q 'from web import WebMirror' "$mirror_dir/mirror.py" &&
   grep -q 'web-start' "$mirror_dir/cli.py"; then
  :
elif grep -q 'from web import WebMirror' "$mirror_dir/mirror.py" ||
     grep -q 'web-start' "$mirror_dir/cli.py"; then
  echo 'The mirror has a partial browser integration; inspect it before installing.' >&2
  exit 1
else
  patch --dry-run -d "$mirror_dir" -p0 < "$source_dir/iphone_mirror_integration.patch"
  patch -d "$mirror_dir" -p0 < "$source_dir/iphone_mirror_integration.patch"
fi

ln -sfn "$source_dir/iphone_mirror_web.py" "$mirror_dir/web.py"
ln -sfn "$source_dir/iphone_mirror_ocr.py" "$mirror_dir/iphone_mirror_ocr.py"
unit_dir="$HOME/.config/systemd/user/iphone-mirror.service.d"
mkdir -p "$unit_dir"
cp "$source_dir/iphone_mirror_recovery.conf" "$unit_dir/web-recovery.conf"
systemctl --user daemon-reload
"$mirror_dir/venv/bin/python" -m py_compile "$mirror_dir/mirror.py" "$mirror_dir/cli.py" "$mirror_dir/web.py" "$mirror_dir/iphone_mirror_ocr.py"
echo 'Browser mirror installed. Run: iphone-mirror web-start'
