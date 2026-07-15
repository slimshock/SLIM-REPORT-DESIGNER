#!/usr/bin/env sh
set -eu

demo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$demo_root/../.." && pwd)
venv_root="$demo_root/.venv-demo"

if [ ! -x "$venv_root/bin/python" ]; then
    "${PYTHON:-python3}" -m venv "$venv_root"
fi

"$venv_root/bin/python" -m pip install \
    -e "$repo_root/packages/slim_report_core[mysql,sqlalchemy]" \
    -e "$repo_root/packages/slim_report_designer_ui" \
    -e "$repo_root/packages/slim_report_flask[database]" \
    -r "$demo_root/requirements.txt"

exec "$venv_root/bin/python" "$demo_root/app.py"
