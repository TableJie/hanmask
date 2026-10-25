# Sourced by the hooks: prefer the project venv so `hanmask` is importable.
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
