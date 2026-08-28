"""Print the directory molecule-plugins' Vagrant driver bundles its own
Ansible `vagrant` module in, or nothing if molecule-plugins[vagrant]
isn't installed.

Run from inside WSL, inside the venv at config.WSL_TOOLS_VENV
(molecule_runner.py sources its activate script before calling this).
Exists as a real file rather than an inline `python3 -c "..."` string
because embedding quote characters in a command string that crosses the
Windows subprocess -> wsl.exe -> WSL bash boundary reliably corrupts them
(confirmed empirically - see docs/METHODOLOGY.md week 4). A bare file
path has no quotes to mangle.
"""

import importlib.util
import os

spec = importlib.util.find_spec("molecule_plugins.vagrant")
if spec is not None and spec.origin is not None:
    print(os.path.join(os.path.dirname(spec.origin), "modules"))
