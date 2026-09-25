# Employee Performance and Recruitment-Risk Dashboard

This project gives manufacturing managers one read-only view of employee
performance history and predicted recruitment risk. Managers can switch between
an individual employee and a team, review cumulative positive and negative
performance events, see recruitment-risk probability, and read associated
manager notes.

The project is the final dashboard for Udacity's Data Scientist Nanodegree
software-engineering module.

## Project status

The package, dashboard, tests, launcher, source-distribution build, and CI
workflows are implemented. The commands in [Test and lint](#test-and-lint) and
[Build and inspect the package](#build-and-inspect-the-package) reproduce the
automated acceptance checks locally.

### Submission verification

Before sharing the public repository URL, confirm both of these final delivery
conditions:

- `python-package/dist/employee_events-0.0.tar.gz` is visible at that exact path
  in the public repository. A source distribution attached only to a workflow
  run does not satisfy the rubric's repository requirement.
- Both the lint and test/build workflows are green for the exact revision being
  submitted. The test/build workflow includes the full test suite, a live
  dashboard smoke test, archive inspection, and a clean installation of the
  packaged artifact.

## How it works

The browser-facing application is built with FastHTML. Its components request
data through the installed `employee_events` package, never through dashboard
SQL. The package opens its bundled SQLite database for each query and closes
the connection immediately afterward. A supplied scikit-learn classifier turns
each employee's ordered `positive_events` and `negative_events` totals into a
positive-class probability.

For a team, the dashboard predicts every team member separately and displays
the arithmetic mean of those probabilities. It does not predict from a single
team-wide aggregate.

```text
Browser -> FastHTML routes -> dashboard components -> employee_events package
                                                       |-> SQLite database
Dashboard recruitment-risk chart ---------------------> scikit-learn model
```

Important paths:

- `python-package/employee_events/` — public query API and packaged database
- `report/` — FastHTML application and reusable UI components
- `assets/` — stylesheet and immutable trained model
- `tests/` — database, package, component, and route tests
- `.github/workflows/` — lint and test/build automation
- `project_instructions/` — original scenario and rubric

## Prerequisites

- Python 3.12.14 (the documented and CI version)
- A POSIX-compatible shell for the `start` launcher
- Bash for the copyable CI-equivalent verification blocks
- Network access for the first dependency installation

The standalone `employee_events` package supports Python 3.10 and newer. The
complete project standardizes on Python 3.12.14 so local development and CI use
the same tested interpreter; the pinned Fastcore release also supports Python
3.10 and newer.

## Install

From the project root, create an isolated environment and install the pinned
top-level project dependencies plus the local package:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

If `python3.12` is not on the local path, invoke another Python 3.12 executable
for the first command.

The root requirements file installs `python-package/` in editable mode and
installs a pinned Setuptools version for the rubric-required `setup.py` build.
An import therefore uses the same package code you are editing while still
proving that dashboard imports go through the installed package interface.
FastHTML, Fastcore, Starlette, `httpx2`, and the multipart parser are pinned as
one compatibility set; these pins must be updated and tested together.

## Run the dashboard

Start the application from the project root:

```bash
./start
```

Then open <http://localhost:5001>. The direct equivalent is:

```bash
cd report
python dashboard.py
```

The launcher uses `.venv/bin/python` when it exists, changes to the `report/`
directory, and starts the import-safe application module.

### Routes

| Method and path | Behavior |
| --- | --- |
| `GET /` | Employee 1 report |
| `GET /employee/{id}` | Validated employee report |
| `GET /team/{id}` | Validated team report |
| `GET /update_dropdown?profile_type=Employee` | Employee selector fragment |
| `GET /update_dropdown?profile_type=Team` | Team selector fragment |
| `POST /update_data` | Validates the form and redirects with status 303 |
| `GET /assets/report.css` | Dashboard stylesheet |

Path IDs must be positive integers that exist in the database. Invalid or
unknown IDs, including malformed selected-ID values, return 404. Missing or
blank form fields and unknown profile types return 400.

## Query API

The package exports only its supported public classes:

```python
from employee_events import Employee, QueryBase, QueryMixin, Team

employees = Employee()
print(employees.names())
print(employees.username(1))
print(employees.event_counts(1).head())
print(employees.notes(1))
print(employees.model_data(1))

teams = Team()
print(teams.names())
print(teams.model_data(1))
```

`QueryMixin.query()` returns `list[tuple]`; `pandas_query()` returns a Pandas
`DataFrame`. Entity values are SQLite parameters. Only the controlled class
attribute used for table and column names is interpolated into shared queries.

## Test and lint

With the virtual environment active, run the same local quality gates used by
automation:

```bash
python -m compileall -q python-package/employee_events report tests
python -m flake8 python-package/setup.py python-package/employee_events report tests
python -m pytest -q
```

The suite verifies the immutable database, SQL contracts, feature ordering,
dashboard components, HTTP responses, static asset serving, form validation,
and repeated-render isolation. Matplotlib uses a noninteractive backend during
normal dashboard rendering and tests.

Run the same process-level launcher smoke test used in CI from the project
root. It uses port `8765`, waits for the server, checks representative employee,
team, and CSS responses, and terminates only the process it started:

```bash
set -euo pipefail
dashboard_log=$(mktemp)
PORT=8765 ./start >"$dashboard_log" 2>&1 &
server_pid=$!

cleanup() {
    status=$?
    trap - EXIT
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
    if [ "$status" -ne 0 ]; then
        cat "$dashboard_log" || true
    fi
    rm -f "$dashboard_log" || true
    exit "$status"
}
trap cleanup EXIT

python - <<'PY'
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

base_url = "http://127.0.0.1:8765"
deadline = monotonic() + 45
last_error = None

while monotonic() < deadline:
    try:
        with urlopen(f"{base_url}/", timeout=5) as response:
            if response.status == 200:
                break
    except (OSError, URLError) as error:
        last_error = error
    sleep(1)
else:
    raise RuntimeError("dashboard did not start within 45 seconds") from last_error

expected_content = {
    "/": b"Employee Performance",
    "/employee/1": b"Employee Performance",
    "/team/1": b"Team Performance",
    "/assets/report.css": b".container",
}
for path, marker in expected_content.items():
    with urlopen(f"{base_url}{path}", timeout=30) as response:
        body = response.read()
        assert response.status == 200, (path, response.status)
        assert marker in body, (path, marker)
PY
```

## Build and inspect the package

The course rubric requires the legacy `setup.py` source-distribution path:

```bash
cd python-package
python setup.py sdist
cd ..
tar -tzf python-package/dist/employee_events-*.tar.gz
```

The archive must contain `employee_events/employee_events.db`. Run the following
from the project root to prove that the artifact installs with its declared
dependencies, imports outside the source checkout, and queries its own bundled
database:

```bash
archive_path="$PWD/python-package/dist/employee_events-0.0.tar.gz"
test -f "$archive_path"
artifact_check_dir=$(mktemp -d)
python3.12 -m venv "$artifact_check_dir/venv"
"$artifact_check_dir/venv/bin/python" -m pip install --upgrade pip
"$artifact_check_dir/venv/bin/python" -m pip install "$archive_path"
"$artifact_check_dir/venv/bin/python" -m pip check
(
    cd "$artifact_check_dir"
    "$artifact_check_dir/venv/bin/python" - <<'PY'
from pathlib import Path

import employee_events
from employee_events import Employee, QueryBase, QueryMixin, Team
from employee_events.sql_execution import db_path

package_path = Path(employee_events.__file__).resolve().parent
assert package_path == db_path.parent
assert db_path.is_file()
assert Employee().username(1)
assert not Employee().event_counts(1).empty
assert Team().username(1)
assert issubclass(QueryBase, QueryMixin)
PY
)
```

The source distribution is a required repository deliverable, not merely a CI
artifact. Before submission, open the public repository and confirm that
`python-package/dist/employee_events-0.0.tar.gz` is visible at that exact path.

## Fixture policy

Treat these files as immutable, authoritative fixtures:

- `assets/model.pkl`
- `python-package/employee_events/employee_events.db`
- `src/generated_data/*`

Do not run `src/build_project_assets.py` during installation, testing, CI, or
normal development. It is an unseeded generator that overwrites the canonical
database and model. Some supplied event rows contain negative counts; queries
and charts intentionally preserve those values rather than silently cleaning
them.

## Continuous integration

The lint workflow compiles and checks the package, dashboard, and test code with
the pinned Flake8 release. The test/build workflow installs the pinned top-level
environment, runs `pip check` and pytest, smoke-tests `./start`, builds and
inspects the source distribution, installs the artifact in a separate clean
environment, runs an out-of-tree query, and uploads the verified tarball.

Both workflows run for every pushed commit and for pull requests whose target
branch is `main`.

## Troubleshooting

- If model loading reports a scikit-learn version warning, recreate `.venv` and
  install the exact versions from `requirements.txt`.
- If port 5001 is already in use, stop the specific process using that port
  before starting the dashboard again.
- If `employee_events` cannot be imported, activate `.venv` and rerun
  `python -m pip install -r requirements.txt` from the project root.
- If the package works only inside `python-package/`, the editable installation
  is missing; reinstall the root requirements and verify with `python -m pip
  check`.

## License

The supplied educational content is copyright Udacity, Inc. and is provided
under the terms in [LICENSE.txt](LICENSE.txt), including the stated Creative
Commons Attribution-NonCommercial-NoDerivs conditions and Udacity Terms of Use.
