from copy import deepcopy
import math

from employee_events import Employee, QueryBase, Team
from fasthtml.common import Div, FastHTML, H1, Link, Title, serve
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, RedirectResponse

from base_components import (
    BaseComponent,
    DataTable,
    Dropdown,
    MatplotlibViz,
    Radio,
)
from combined_components import CombinedComponent, FormGroup
from matplotlib import pyplot as plt
from utils import load_model, project_root


MODEL_FEATURES = ["positive_events", "negative_events"]
POSITIVE_CLASS_LABEL = 1


def _profile_title(model):
    return f"{model.name.title()} Performance"


class ReportDropdown(Dropdown):
    def build_component(self, entity_id, model):
        self.label = model.name.title()
        return super().build_component(entity_id, model)

    def component_data(self, entity_id, model):
        return model.names()


class Header(BaseComponent):
    def build_component(self, entity_id, model):
        return H1(_profile_title(model))


class LineChart(MatplotlibViz):
    def visualization(self, entity_id, model):
        event_counts = model.event_counts(entity_id).fillna(0)
        required_columns = ["event_date", *MODEL_FEATURES]
        missing_columns = [
            column
            for column in required_columns
            if column not in event_counts.columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            message = f"Event data is missing required columns: {missing}"
            raise ValueError(message)

        cumulative_counts = (
            event_counts.loc[:, required_columns]
            .set_index("event_date")
            .sort_index()
            .loc[:, MODEL_FEATURES]
            .cumsum()
        )
        cumulative_counts.columns = ["Positive", "Negative"]

        figure, axis = plt.subplots(figsize=(8, 4.5))
        if cumulative_counts.empty:
            axis.text(
                0.5,
                0.5,
                "No performance events available",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            self.summary_text = "No performance events are available."
        else:
            cumulative_counts.plot(
                ax=axis,
                color=["#247a3c", "#b52a2a"],
                linewidth=2.5,
            )
            final_counts = cumulative_counts.iloc[-1]
            positive_total = float(final_counts["Positive"])
            negative_total = float(final_counts["Negative"])
            self.summary_text = (
                "Cumulative totals: "
                f"{positive_total:g} positive and "
                f"{negative_total:g} negative events."
            )

        self.alt_text = (
            f"Cumulative {model.name} performance-events line chart. "
            f"{self.summary_text}"
        )

        axis.set_title(
            f"Cumulative {model.name.title()} Performance Events",
            fontsize=16,
        )
        axis.set_xlabel("Date")
        axis.set_ylabel("Cumulative Event Count")
        self.set_axis_styling(
            axis,
            bordercolor="black",
            fontcolor="black",
        )
        figure.tight_layout()
        return figure


class BarChart(MatplotlibViz):
    predictor = load_model()

    def positive_class_index(self):
        classes = getattr(self.predictor, "classes_", None)
        if classes is None:
            raise ValueError("Predictor does not define class labels")

        try:
            class_labels = tuple(classes)
        except TypeError:
            raise ValueError(
                "Predictor class labels are invalid"
            ) from None

        if len(class_labels) != 2:
            raise ValueError("Predictor must be a binary classifier")

        matches = [
            index
            for index, label in enumerate(class_labels)
            if label == POSITIVE_CLASS_LABEL
        ]
        if len(matches) != 1:
            raise ValueError(
                "Predictor does not define the positive recruitment class"
            )

        return matches[0], len(class_labels)

    def visualization(self, entity_id, model):
        model_data = model.model_data(entity_id)
        missing_columns = [
            column
            for column in MODEL_FEATURES
            if column not in model_data.columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            message = f"Model data is missing required columns: {missing}"
            raise ValueError(message)

        features = model_data.loc[:, MODEL_FEATURES]
        figure, axis = plt.subplots(figsize=(8, 4.5))

        if features.empty or features.isnull().to_numpy().any():
            axis.text(
                0.5,
                0.5,
                "Recruitment risk unavailable",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            self.summary_text = "Predicted recruitment risk is unavailable."
        else:
            positive_class_index, class_count = self.positive_class_index()
            probabilities = self.predictor.predict_proba(features)
            if (
                probabilities.ndim != 2
                or probabilities.shape[0] != len(features)
                or probabilities.shape[1] != class_count
            ):
                message = "Predictor returned an invalid probability array"
                raise ValueError(message)

            positive_probabilities = probabilities[:, positive_class_index]
            if model.name == "team":
                risk = float(positive_probabilities.mean())
            else:
                risk = float(positive_probabilities[0])

            if not math.isfinite(risk) or not 0 <= risk <= 1:
                message = "Predictor returned risk outside the range [0, 1]"
                raise ValueError(message)

            risk_color = plt.get_cmap("RdYlGn_r")(risk)
            axis.barh(
                ["Recruitment risk"],
                [risk],
                color=[risk_color],
                height=0.45,
            )

            if risk >= 0.85:
                label_x = risk - 0.02
                horizontal_alignment = "right"
                label_color = "white"
            else:
                label_x = risk + 0.02
                horizontal_alignment = "left"
                label_color = "black"

            axis.text(
                label_x,
                0,
                f"{risk:.1%}",
                color=label_color,
                fontweight="bold",
                ha=horizontal_alignment,
                va="center",
            )
            self.summary_text = (
                f"Predicted {model.name} recruitment risk: {risk:.1%}."
            )

        self.alt_text = (
            "Predicted recruitment-risk horizontal bar chart. "
            f"{self.summary_text}"
        )

        axis.set_xlim(0, 1)
        axis.set_xticks([0, 0.25, 0.5, 0.75, 1])
        axis.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
        axis.set_title("Predicted Recruitment Risk", fontsize=16)
        axis.set_xlabel("Probability")
        axis.set_ylabel("")
        self.set_axis_styling(
            axis,
            bordercolor="black",
            fontcolor="black",
        )
        figure.tight_layout()
        return figure


class Visualizations(CombinedComponent):
    children = [LineChart(), BarChart()]
    outer_div_type = Div(cls="grid")


class NotesTable(DataTable):
    caption = "Manager notes"

    def component_data(self, entity_id, model):
        return model.notes(entity_id)


class DashboardFilters(FormGroup):
    id = "top-filters"
    action = "/update_data"
    method = "POST"
    children = [
        Radio(
            values=["Employee", "Team"],
            name="profile_type",
            hx_get="/update_dropdown",
            hx_target="#selector-wrapper",
            hx_swap="outerHTML",
        ),
        ReportDropdown(id="selector", name="user-selection"),
    ]


class Report(CombinedComponent):
    children = [
        Header(),
        DashboardFilters(),
        Visualizations(),
        NotesTable(),
    ]


REPORT_CSS_PATH = project_root / "assets" / "report.css"
app = FastHTML(
    title="Employee Performance and Recruitment Risk",
    hdrs=(
        Link(
            rel="stylesheet",
            href="/assets/report.css",
            type="text/css",
        ),
    ),
    htmlkw={"lang": "en"},
    sess_cls=None,
    secret_key="dashboard-without-sessions",
)

report = Report()
PROFILE_MODELS = {"Employee": Employee, "Team": Team}


@app.get("/assets/report.css")
def report_stylesheet():
    return FileResponse(REPORT_CSS_PATH, media_type="text/css")


def _profile_model(profile_type):
    model_class = PROFILE_MODELS.get(profile_type)
    if model_class is None:
        raise HTTPException(status_code=400, detail="Unknown profile type")
    return model_class()


def _validated_entity_id(raw_value, model: QueryBase):
    if isinstance(raw_value, bool):
        raise HTTPException(status_code=404, detail="Entity not found")

    try:
        entity_id = int(raw_value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=404,
            detail="Entity not found",
        ) from None

    if entity_id <= 0:
        raise HTTPException(status_code=404, detail="Entity not found")

    valid_ids = {int(value) for _, value in model.names()}
    if entity_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Entity not found")

    return entity_id


def _render_report(raw_value, model: QueryBase):
    entity_id = _validated_entity_id(raw_value, model)
    return Title(_profile_title(model)), report(entity_id, model)


@app.get("/")
def index():
    return _render_report(1, Employee())


@app.get("/employee/{employee_id}")
def employee(employee_id: str):
    return _render_report(employee_id, Employee())


@app.get("/team/{team_id}")
def team(team_id: str):
    return _render_report(team_id, Team())


@app.get("/update_dropdown")
def update_dropdown(profile_type: str):
    model = _profile_model(profile_type)
    dropdown = deepcopy(DashboardFilters.children[1])
    return dropdown(None, model)


@app.post("/update_data")
async def update_data(request: Request):
    form_data = await request.form()
    profile_type = form_data.get("profile_type")
    raw_entity_id = form_data.get("user-selection")

    if not isinstance(profile_type, str) or not profile_type:
        raise HTTPException(status_code=400, detail="Missing profile type")
    if not isinstance(raw_entity_id, str) or not raw_entity_id.strip():
        raise HTTPException(status_code=400, detail="Missing entity selection")

    model = _profile_model(profile_type)
    entity_id = _validated_entity_id(raw_entity_id, model)
    return RedirectResponse(
        url=f"/{model.name}/{entity_id}",
        status_code=303,
    )


if __name__ == "__main__":
    serve(reload=False)
