#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        parser.error("pass the packaged Manager command after --")

    with tempfile.TemporaryDirectory(prefix="umm-extractor-host-") as temporary:
        root = Path(temporary)
        project = root / "umadump-fixture"
        inbox = root / "inbox"
        project.mkdir()
        script = project / "main.py"
        script.write_text(
            "import json,os,sys\n"
            "from pathlib import Path\n"
            "Path('packaged-host-result.json').write_text(json.dumps({"
            "'argv':sys.argv[1:],'cwd':os.getcwd()}),encoding='utf-8')\n",
            encoding="utf-8",
        )
        for name in ("memory.py", "game_structs.py", "json_encoders.py"):
            (project / name).write_text("", encoding="utf-8")
        (project / "requirements.txt").write_text(
            "minidump~=0.0.24\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                *command,
                "--extractor-host",
                str(project),
                str(script),
                str(inbox),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise SystemExit(
                "Packaged extractor host failed\n"
                f"command={command!r}\n"
                f"stdout={result.stdout}\n"
                f"stderr={result.stderr}"
            )
        output = inbox / "packaged-host-result.json"
        if not output.is_file():
            raise SystemExit(
                "Packaged extractor host produced no fixture output\n"
                f"stdout={result.stdout}\n"
                f"stderr={result.stderr}"
            )
        payload = json.loads(output.read_text(encoding="utf-8"))
        expected_argv = ["--rerun-mode", "once", "--no-update-check"]
        if payload.get("argv") != expected_argv:
            raise SystemExit(f"Unexpected hosted argv: {payload!r}")
        if Path(str(payload.get("cwd"))).resolve() != inbox.resolve():
            raise SystemExit(f"Unexpected hosted cwd: {payload!r}")
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
