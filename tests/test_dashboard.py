import base64
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
import sys
from types import SimpleNamespace
from urllib.parse import quote

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "report"
DB_PATH = (
    PROJECT_ROOT
    / "python-package"
    / "employee_events"
    / "employee_events.db"
)
MODEL_PATH = PROJECT_ROOT / "assets" / "model.pkl"
EXPECTED_MODEL_SHA256 = (
    "06fa2c4793dde45e860f4fa58d8a09218b973ea8b96e5e8bee16b1d09d335c4b"
)
sys.path.insert(0, str(REPORT_PATH))

# dashboard.py intentionally uses report/ as its script-style import root.
import dashboard  # noqa: E402


PNG_DATA_PATTERN = re.compile(
    r"data:image/png;base64,([A-Za-z0-9+/=]+)"
)
TABLE_NAMES = ("employee", "team", "employee_events", "notes")


@pytest.fixture(scope="module")
def client():
    with TestClient(
        dashboard.app,
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


def _png_payloads(html):
    payloads = PNG_DATA_PATTERN.findall(html)
    for payload in payloads:
        image = base64.b64decode(payload, validate=True)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(image) > 100
    return payloads


def _database_counts():
    database_uri = f"{DB_PATH.as_uri()}?mode=ro&immutable=1"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        return {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in TABLE_NAMES
        }


def _assert_full_report(response, title, note_fragment):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="en"' in response.text
    assert len(
        re.findall(r'<meta\b[^>]*\bcharset="utf-8"', response.text)
    ) == 1
    assert len(
        re.findall(r'<meta\b[^>]*\bname="viewport"', response.text)
    ) == 1
    head = re.search(r"<head>(.*?)</head>", response.text, re.DOTALL)
    body = re.search(r"<body>(.*?)</body>", response.text, re.DOTALL)
    assert head is not None
    assert body is not None
    assert re.findall(r"<title>(.*?)</title>", head.group(1)) == [title]
    assert re.findall(r"<h1>(.*?)</h1>", body.group(1)) == [title]
    assert "Employee Performance and Recruitment Risk" not in response.text
    assert note_fragment in response.text
    assert "note_date" in response.text
    assert len(_png_payloads(response.text)) == 2
    image_alternatives = re.findall(
        r'<img\b[^>]*\balt="([^"]+)"',
        response.text,
    )
    assert len(image_alternatives) == 2
    assert any(
        "performance-events line chart" in text
        for text in image_alternatives
    )
    assert any(
        "recruitment-risk horizontal bar chart" in text
        for text in image_alternatives
    )
    assert 'class="visualization-summary"' in response.text
    assert "Cumulative totals:" in response.text
    assert "Predicted employee recruitment risk:" in response.text or (
        "Predicted team recruitment risk:" in response.text
    )
    assert "<caption>Manager notes</caption>" in response.text
    assert "<thead>" in response.text
    assert "<tbody>" in response.text
    assert len(re.findall(r'<th\b[^>]*\bscope="col"', response.text)) == 2


class RecordingPredictor:
    def __init__(self, probabilities, classes=(1, 0)):
        self.classes_ = np.asarray(classes)
        self.probabilities = np.asarray(probabilities, dtype=float)
        self.frames = []

    def predict_proba(self, frame):
        self.frames.append(frame.copy())
        return self.probabilities.copy()


class ChartModel:
    def __init__(
        self,
        name,
        event_frame=None,
        model_frame=None,
    ):
        self.name = name
        self.event_frame = event_frame
        self.model_frame = model_frame

    def event_counts(self, entity_id):
        return self.event_frame.copy()

    def model_data(self, entity_id):
        return self.model_frame.copy()


def test_dashboard_import_is_safe():
    assert dashboard.app is not None
    assert dashboard.report is not None
    assert dashboard.__name__ == "dashboard"


def test_model_fixture_checksum():
    assert MODEL_PATH.is_file()
    assert sha256(MODEL_PATH.read_bytes()).hexdigest() == (
        EXPECTED_MODEL_SHA256
    )


def test_line_chart_sorts_dates_and_plots_chronological_cumulative_values():
    event_frame = pd.DataFrame(
        {
            "event_date": ["2024-01-03", "2024-01-01", "2024-01-02"],
            "positive_events": [3, 1, 2],
            "negative_events": [1, 4, 2],
        }
    )
    model = ChartModel("employee", event_frame=event_frame)
    chart = dashboard.LineChart()
    figure = chart.visualization(7, model)

    try:
        axis = figure.axes[0]
        lines = axis.get_lines()

        assert len(lines) == 2
        assert [line.get_label() for line in lines] == ["Positive", "Negative"]
        np.testing.assert_allclose(lines[0].get_ydata(), [1, 3, 6])
        np.testing.assert_allclose(lines[1].get_ydata(), [4, 6, 7])
        assert axis.get_title() == "Cumulative Employee Performance Events"
        assert axis.get_xlabel() == "Date"
        assert axis.get_ylabel() == "Cumulative Event Count"
        assert chart.summary_text == (
            "Cumulative totals: 6 positive and 7 negative events."
        )
        assert chart.alt_text == (
            "Cumulative employee performance-events line chart. "
            "Cumulative totals: 6 positive and 7 negative events."
        )
    finally:
        dashboard.plt.close(figure)


@pytest.mark.parametrize(
    ("profile_name", "probabilities", "expected_risk"),
    [
        ("employee", [[0.2, 0.8]], 0.2),
        ("team", [[0.2, 0.8], [0.6, 0.4]], 0.4),
    ],
)
def test_bar_chart_uses_positive_label_feature_order_and_profile_risk(
    profile_name,
    probabilities,
    expected_risk,
):
    row_count = len(probabilities)
    model_frame = pd.DataFrame(
        {
            "unused": list(range(row_count)),
            "negative_events": [4] * row_count,
            "positive_events": [9] * row_count,
        }
    )
    model = ChartModel(profile_name, model_frame=model_frame)
    predictor = RecordingPredictor(probabilities, classes=(1, 0))
    chart = dashboard.BarChart()
    chart.predictor = predictor
    figure = chart.visualization(3, model)

    try:
        axis = figure.axes[0]
        bar = axis.patches[0]

        assert len(predictor.frames) == 1
        assert predictor.frames[0].columns.tolist() == dashboard.MODEL_FEATURES
        assert predictor.frames[0].to_dict("records") == [
            {"positive_events": 9, "negative_events": 4}
        ] * row_count
        assert bar.get_width() == pytest.approx(expected_risk)
        assert bar.get_facecolor() == pytest.approx(
            dashboard.plt.get_cmap("RdYlGn_r")(expected_risk)
        )
        assert axis.get_xlim() == pytest.approx((0, 1))
        assert [tick.get_text() for tick in axis.get_xticklabels()] == [
            "0%",
            "25%",
            "50%",
            "75%",
            "100%",
        ]
        expected_percentage = f"{expected_risk:.1%}"
        assert expected_percentage in [text.get_text() for text in axis.texts]
        assert chart.summary_text == (
            f"Predicted {profile_name} recruitment risk: "
            f"{expected_percentage}."
        )
        assert expected_percentage in chart.alt_text
    finally:
        dashboard.plt.close(figure)


@pytest.mark.parametrize(
    ("predictor", "message"),
    [
        (SimpleNamespace(), "does not define class labels"),
        (SimpleNamespace(classes_=1), "class labels are invalid"),
        (SimpleNamespace(classes_=[0, 1, 2]), "binary classifier"),
        (
            SimpleNamespace(classes_=[0, 2]),
            "does not define the positive recruitment class",
        ),
    ],
)
def test_bar_chart_rejects_invalid_classifier_metadata(predictor, message):
    chart = dashboard.BarChart()
    chart.predictor = predictor

    with pytest.raises(ValueError, match=message):
        chart.positive_class_index()


def test_bar_chart_finds_positive_label_when_class_order_is_reversed():
    chart = dashboard.BarChart()
    chart.predictor = SimpleNamespace(classes_=np.asarray([1, 0]))

    assert chart.positive_class_index() == (0, 2)


@pytest.mark.parametrize(
    "model_frame",
    [
        pd.DataFrame(columns=dashboard.MODEL_FEATURES),
        pd.DataFrame(
            {
                "positive_events": [None],
                "negative_events": [None],
            }
        ),
        pd.DataFrame(
            {
                "positive_events": [7],
                "negative_events": [None],
            }
        ),
    ],
)
def test_bar_chart_gracefully_handles_unavailable_feature_data(model_frame):
    model = ChartModel("employee", model_frame=model_frame)
    predictor = RecordingPredictor([[0.25, 0.75]])
    chart = dashboard.BarChart()
    chart.predictor = predictor
    figure = chart.visualization(1, model)

    try:
        axis = figure.axes[0]

        assert predictor.frames == []
        assert len(axis.patches) == 0
        assert "Recruitment risk unavailable" in [
            text.get_text() for text in axis.texts
        ]
        assert chart.summary_text == (
            "Predicted recruitment risk is unavailable."
        )
        assert chart.summary_text in chart.alt_text
    finally:
        dashboard.plt.close(figure)


def test_team_risk_is_unavailable_when_any_member_data_is_incomplete():
    model_frame = pd.DataFrame(
        {
            "positive_events": [9, None, 4],
            "negative_events": [4, 2, 1],
        }
    )
    model = ChartModel("team", model_frame=model_frame)
    predictor = RecordingPredictor([[0.2, 0.8]], classes=(1, 0))
    chart = dashboard.BarChart()
    chart.predictor = predictor
    figure = chart.visualization(1, model)

    try:
        assert predictor.frames == []
        assert len(figure.axes[0].patches) == 0
        assert chart.summary_text == (
            "Predicted recruitment risk is unavailable."
        )
    finally:
        dashboard.plt.close(figure)


@pytest.mark.parametrize(
    ("path", "title", "note_fragment"),
    [
        (
            "/",
            "Employee Performance",
            "Completed a task ahead of schedule",
        ),
        (
            "/employee/1",
            "Employee Performance",
            "Completed a task ahead of schedule",
        ),
        (
            "/team/1",
            "Team Performance",
            "Always offers to help colleagues",
        ),
    ],
)
def test_full_report_routes(client, path, title, note_fragment):
    response = client.get(path)
    _assert_full_report(response, title, note_fragment)


def test_only_the_stylesheet_is_served_from_assets(client):
    response = client.get("/assets/report.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.text.strip()
    assert client.get("/assets/").status_code == 404
    assert client.get("/assets/model.pkl").status_code == 404
    assert client.get("/report.css").status_code == 404


@pytest.mark.parametrize(
    ("profile_type", "expected_count", "expected_name", "absent_name"),
    [
        ("Employee", 25, "Alex Martinez", "Alpha Team"),
        ("Team", 5, "Alpha Team", "Alex Martinez"),
    ],
)
def test_dropdown_fragments_contain_expected_options(
    client,
    profile_type,
    expected_count,
    expected_name,
    absent_name,
):
    response = client.get(
        "/update_dropdown",
        params={"profile_type": profile_type},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.text.count("<option") == expected_count
    assert expected_name in response.text
    assert absent_name not in response.text
    assert 'name="user-selection"' in response.text
    assert response.text.count('id="selector-wrapper"') == 1
    assert response.text.count('id="selector"') == 1
    assert '<label for="selector">' in response.text

    first_option = re.search(r"<option\b[^>]*>", response.text)
    assert first_option is not None
    assert 'value="1"' in first_option.group(0)
    assert "selected" in first_option.group(0)
    assert len(re.findall(r"<option\b[^>]*\bselected", response.text)) == 1


def test_full_page_selector_uses_outer_html_swap_and_selected_entity(client):
    response = client.get("/employee/3")

    assert response.status_code == 200
    assert response.text.count('hx-target="#selector-wrapper"') == 2
    assert response.text.count('hx-swap="outerHTML"') == 2
    assert response.text.count('id="selector-wrapper"') == 1
    assert response.text.count('id="selector"') == 1
    assert '<label for="selector">Employee</label>' in response.text

    selected_options = re.findall(
        r"<option\b[^>]*\bselected[^>]*>",
        response.text,
    )
    assert len(selected_options) == 1
    assert 'value="3"' in selected_options[0]


@pytest.mark.parametrize(
    ("profile_type", "entity_id", "expected_location"),
    [
        ("Employee", "1", "/employee/1"),
        ("Team", "1", "/team/1"),
    ],
)
def test_valid_form_submissions_redirect(
    client,
    profile_type,
    entity_id,
    expected_location,
):
    response = client.post(
        "/update_data",
        data={
            "profile_type": profile_type,
            "user-selection": entity_id,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == expected_location


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"profile_type": ""},
        {"profile_type": "Unknown"},
        {"profile_type": "employee"},
    ],
)
def test_invalid_dropdown_requests_return_400(client, params):
    response = client.get(
        "/update_dropdown",
        params=params,
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/employee/",
        "/employee/0",
        "/employee/-1",
        "/employee/999",
        "/employee/not-a-number",
        "/team/0",
        "/team/-1",
        "/team/999",
        "/team/not-a-number",
        "/employee/" + quote("1' OR 1=1--", safe=""),
    ],
)
def test_invalid_entity_routes_return_404(client, path):
    response = client.get(path)
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("form_data", "expected_status"),
    [
        ({}, 400),
        ({"profile_type": "Employee"}, 400),
        ({"user-selection": "1"}, 400),
        ({"profile_type": "Unknown", "user-selection": "1"}, 400),
        ({"profile_type": "Employee", "user-selection": ""}, 400),
        ({"profile_type": "Employee", "user-selection": "0"}, 404),
        ({"profile_type": "Team", "user-selection": "-1"}, 404),
        ({"profile_type": "Employee", "user-selection": "999"}, 404),
        ({"profile_type": "Team", "user-selection": "not-a-number"}, 404),
        (
            {
                "profile_type": "Employee",
                "user-selection": "1' OR 1=1--",
            },
            404,
        ),
    ],
)
def test_invalid_form_submissions_return_intentional_errors(
    client,
    form_data,
    expected_status,
):
    response = client.post(
        "/update_data",
        data=form_data,
        follow_redirects=False,
    )

    assert response.status_code == expected_status
    assert response.status_code != 500


def test_invalid_requests_do_not_modify_database(client):
    counts_before = _database_counts()
    injection = quote("1'; DROP TABLE employee;--", safe="")

    invalid_gets = [
        "/employee/0",
        "/team/999",
        f"/employee/{injection}",
    ]
    for path in invalid_gets:
        assert client.get(path).status_code == 404

    invalid_posts = [
        {},
        {"profile_type": "Unknown", "user-selection": "1"},
        {"profile_type": "Employee", "user-selection": "1 OR 1=1"},
    ]
    for form_data in invalid_posts:
        response = client.post(
            "/update_data",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code in {400, 404}
        assert response.status_code != 500

    assert _database_counts() == counts_before


def test_alternating_renders_do_not_leak_state_or_figures(client):
    initial_figures = set(dashboard.plt.get_fignums())

    for _ in range(2):
        employee_response = client.get("/employee/1")
        _assert_full_report(
            employee_response,
            "Employee Performance",
            "Completed a task ahead of schedule",
        )
        assert "<h1>Team Performance</h1>" not in employee_response.text
        assert "Alpha Team" not in employee_response.text
        assert employee_response.text.count("<option") == 25
        assert employee_response.text.count("<h1") == 1
        assert employee_response.text.count("<form") == 1
        assert employee_response.text.count("<table") == 1

        team_response = client.get("/team/1")
        _assert_full_report(
            team_response,
            "Team Performance",
            "Always offers to help colleagues",
        )
        assert "<h1>Employee Performance</h1>" not in team_response.text
        assert "Alex Martinez" not in team_response.text
        assert team_response.text.count("<option") == 5
        assert team_response.text.count("<h1") == 1
        assert team_response.text.count("<form") == 1
        assert team_response.text.count("<table") == 1

        assert set(dashboard.plt.get_fignums()) == initial_figures

    assert len(dashboard.Report.children) == 4
    assert len(dashboard.DashboardFilters.children) == 2
    assert not dashboard.Report.outer_div_type.children
    assert not dashboard.Visualizations.outer_div_type.children
