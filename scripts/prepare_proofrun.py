#!/usr/bin/env python3
"""Build the two tagged demo releases and write a local ProofRun target registry.

Uses only the standard library, Git, and Docker. This prepares an investigation;
it does not call a model, deploy anything, or claim a ProofRun finding.
"""

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


def command(args, *, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def logged(args, log, *, cwd=None):
    with log.open("w") as output:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Command failed; inspect {log}")
    return log.read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New output directory (default .proofrun/setup)")
    parser.add_argument("--collector-image", default="python:3.12-slim",
                        help="Preloaded trusted Python image, resolved to its immutable ID")
    parser.add_argument("--scope", default="operator", help="Authorized ProofRun workspace scope")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    spec = json.loads((repo / "proofrun-demo.json").read_text())
    output = (args.output or repo / ".proofrun" / "setup").resolve()
    if output.exists():
        parser.error("Output already exists. Choose a new --output directory to preserve prior setup evidence.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", args.scope):
        parser.error("Invalid workspace scope.")
    # Resolve locally; the independent collector is never taken from the demo app image.
    collector = command(["docker", "image", "inspect", "--format", "{{.Id}}", args.collector_image])
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", collector):
        raise RuntimeError("Docker did not return an immutable collector image ID.")
    revisions = {name: command(["git", "rev-parse", f"{ref}^{{commit}}"], cwd=repo)
                 for name, ref in (("baseline", "demo-baseline"), ("candidate", "demo-update"))}
    if revisions["baseline"] == revisions["candidate"]:
        raise RuntimeError("Demo tags must identify different commits.")
    output.mkdir(parents=True)
    images = {}
    checks = {}
    for name, revision in revisions.items():
        print(f"Building {name}: {revision}", flush=True)
        archive = subprocess.run(["git", "archive", "--format=tar", revision], cwd=repo,
                                 check=True, stdout=subprocess.PIPE).stdout
        with tempfile.TemporaryDirectory(prefix="proofrun-demo-build-") as temporary:
            context = Path(temporary)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
                tree.extractall(context, filter="data")
            iidfile = output / f"{name}-image.txt"
            logged(["docker", "build", "--pull=false", "--iidfile", str(iidfile),
                    "--tag", f"{spec['image_name']}:{revision[:12]}", str(context)],
                   output / f"{name}-build.log")
            image_id = iidfile.read_text().strip()
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
                raise RuntimeError("Docker build did not return an immutable image ID.")
            images[revision] = image_id
            log = output / f"{name}-tests.log"
            text = logged(["docker", "run", "--rm", "--network", "none", "--user", "65534:65534",
                           "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                           "--pids-limit", "128", "--memory", "512m", "--cpus", "1",
                           "--tmpfs", "/tmp:rw,nosuid,size=64m", "--workdir", "/workspace",
                           "--env", "PYTHONDONTWRITEBYTECODE=1", "--entrypoint", "python", image_id,
                           "-m", "unittest", "discover", "-s", "tests", "-v"], log)
            match = re.search(r"(?m)^Ran ([1-9][0-9]*) tests? in [0-9.]+s$", text)
            if not match:
                raise RuntimeError(f"No nonzero-test completion marker in {log}")
            checks[name] = {"tests": int(match[1]), "status": "passed", "log": log.name}
            print(f"  {match[1]} original tests passed", flush=True)
    target = {
        "id": spec["id"], "name": spec["name"], "repository": str(repo),
        "workspaces": [args.scope], "images": images,
        "requirements": [{"id": spec["id"] + "-compatibility", "kind": "preserve_response",
                          "description": spec["requirement"], "path_prefix": spec["endpoint"],
                          "methods": ["POST"]}],
        "runtime": {"collector_image": collector,
                    "command": ["python", "-m", spec["module"], "--host", "0.0.0.0", "--port", "8080"],
                    "test_command": ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
                    "workdir": ".", "port": 8080, "health_path": "/health", "startup_seconds": 30,
                    "env": {}},
        "test_paths": ["tests/*"],
        "test_success_pattern": r"(?m)^Ran [1-9][0-9]* tests? in [0-9.]+s$",
        "repair_paths": spec["repair_paths"],
        "exclude_paths": ["README.md", "scripts/*", "proofrun-demo.json", ".github/*", ".proofrun/*"]
    }
    request = {"target_id": spec["id"], "baseline_revision": revisions["baseline"],
               "candidate_revision": revisions["candidate"], "benefit": spec["benefit"],
               "budget_seconds": 300, "repair": True}
    receipt = {"schema": "proofrun-demo-setup.v1", "created_at": datetime.now(timezone.utc).isoformat(),
               "revisions": revisions, "images": images, "collector_image": collector,
               "original_tests": checks, "investigation_executed": False,
               "staging_checked": False, "repair_generated": False}
    for filename, data in (("targets.json", {"targets": [target]}),
                           ("request.json", request), ("setup.json", receipt)):
        (output / filename).write_text(json.dumps(data, indent=2) + "\n")
    print(f"Prepared registry: {output / 'targets.json'}")
    print(f"Prepared request: {output / 'request.json'}")
    print("No model investigation or staging execution has been performed.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
