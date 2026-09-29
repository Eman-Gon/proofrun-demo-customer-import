# Customer import · ProofRun demo

A tiny customer-import API with a browser page and an intentionally seeded
dependency regression. It demonstrates a release that starts successfully and
passes its existing tests while breaking a documented client workflow.

**Scenario:** your client meeting starts in 20 minutes. A dependency upgrade has
reached staging. The client sometimes imports customers without nicknames. Can
you demonstrate that workflow on the new release?

This is a prepared demo, not evidence of a naturally discovered production bug.
It does not deploy to DuploCloud, invoke a model, or create proof by itself.

## Two releases

| Git ref | Dependencies | Expected omitted-nickname behavior |
| --- | --- | --- |
| `demo-baseline` | Pydantic 1.10.18 | HTTP 200, nickname normalized to null |
| `demo-update` | Pydantic 2.8.2 | HTTP 422, invalid_customer |

The `codex/dependency-update` branch changes only dependency pins. Application
source and the existing tests remain identical. All direct and transitive runtime
dependencies are pinned. The base Python Docker tag is not digest-pinned.

The existing test suite covers explicit nicknames, explicit null, invalid input,
and HTTP basics. It deliberately misses the omitted-nickname case. The actual
behavior the client requires lives in `docs/product-contract.md`.

**Keep this presenter README outside the investigator's allowed source paths.**
It explains the intended regression. Let the investigator inspect application
source, existing tests, dependencies, and the product contract to discover cases.
No prepared repair is included in the repository.

## Run locally

Use Python 3.12. These commands run the revision currently checked out:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m customer_service.server --port 8000
```

Open <http://localhost:8000>. The page sends real requests to the local API.
Choose a synthetic example and submit it to inspect the actual response. No data
is stored. Stop the server with Ctrl-C. Reinstall dependencies after changing refs.

## Compare releases with Docker

Build each immutable Git revision directly from an archive:

```sh
git archive demo-baseline | docker build -t proofrun-customer:baseline -
git archive demo-update | docker build -t proofrun-customer:update -
docker run --rm proofrun-customer:baseline python -m unittest discover -s tests -v
docker run --rm proofrun-customer:update python -m unittest discover -s tests -v
docker run --rm -d --name proofrun-customer-baseline -p 127.0.0.1:8011:8000 proofrun-customer:baseline
docker run --rm -d --name proofrun-customer-update -p 127.0.0.1:8012:8000 proofrun-customer:update
```

Open <http://localhost:8011> and <http://localhost:8012>. Submit **Without nickname**
on each page, or compare these requests:

```sh
curl -i http://localhost:8011/customers/import -H 'Content-Type: application/json' -d '{"name":"Avery Chen"}'
curl -i http://localhost:8012/customers/import -H 'Content-Type: application/json' -d '{"name":"Avery Chen"}'
```

Stop your two demo containers when finished:

```sh
docker stop proofrun-customer-baseline proofrun-customer-update
```

## Using it with ProofRun

Use this repository's local absolute path, the exact commits behind `demo-baseline`
and `demo-update`, and an image containing the matching dependency pins for each
revision. The source runs from `/workspace`, including when ProofRun mounts an
isolated copy there. It supports running as a non-root user.

- Startup: `python -m customer_service.server --host 0.0.0.0 --port 8000`
- Health: `GET /health`, port 8000
- Existing tests: `python -m unittest discover -s tests -v`
- Product requirement: preserve the customer-import contract between releases.
- Source paths: `customer_service/`, `tests/`, `docs/product-contract.md`,
  `requirements.txt`, and `Dockerfile`.

Show actual requests, responses, commit IDs, and run artifacts from the
investigation. A proposed patch passing local checks does not mean it has been
reviewed, deployed, or checked in staging. The original update verdict and any
subsequent repair-verification verdict should remain distinguishable.

## Scope

The HTTP server is a small local demonstration, not a production API. It has no
authentication, database, customer secrets, external integrations, or model calls.
It uses only Python's standard library plus Pydantic and its pinned dependencies.

## Prepare this repo for ProofRun

From `main`, use Python 3.12, Git, and a running Docker daemon:

```sh
docker pull python:3.12-slim
python3.12 scripts/prepare_proofrun.py
```

The helper builds both tagged releases from their committed Git trees, runs the
original tests in each image as an unprivileged user with no network, and writes
`.proofrun/setup/targets.json`, `request.json`, and `setup.json`. It resolves the
trusted collector image to an immutable ID. Generated files remain local and
ignored by Git. The helper does not call a model or deploy a repair. For another
preparation, choose a fresh `--output .proofrun/setup-02` directory.

The registry includes the real local repository path, exact revision hashes,
immutable Docker image IDs, startup/test commands, and a general compatibility
requirement. The presenter README and setup scripts are excluded from agent
inspection; the product contract and application source remain included. No
predeclared failing request or prepared repair is passed to the investigator.

In the separate ProofRun checkout, after installing its worker dependencies and
exporting your private `OPENROUTER_API_KEY` and explicit `PROOFRUN_MODEL`, run:

```sh
python3.12 -m src.proofrun.release_api \
  --targets ../proofrun-demo-customer-import/.proofrun/setup/targets.json \
  --once ../proofrun-demo-customer-import/.proofrun/setup/request.json \
  --artifacts .commit-watch/proofrun-demo-customer-import-run-01
```

These relative paths assume the two checkouts are siblings. Use an absolute path
if yours are elsewhere. Select a new artifact directory for every run. A `skip`
verdict exits with code 2; inspect the result artifacts rather than treating that
exit as absence of results. Model access can incur your provider's normal costs.
Do not put keys in this demo repository or in its Docker images.

The default target scope is `operator` for local use. Set `--scope WORKSPACE_ID`
when preparing it for an authorized portal workspace. Portal initiation, remote
hosting, and staging replay require their own actual configuration and evidence.

The default `main` branch contains the working app and setup helper. The
`demo-baseline` and `demo-update` tags stay fixed to the original two releases;
the helper always compares those tags, regardless of later setup-doc changes.
