import base64
from functools import wraps
import io
from threading import RLock

import matplotlib
from fasthtml.common import Div, Img, P

from .base_component import BaseComponent

# The backend must be selected before importing pyplot.
matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

matplotlib.rcParams["savefig.transparent"] = True
matplotlib.rcParams["savefig.format"] = "png"

_RENDER_LOCK = RLock()


def matplotlib2fasthtml(func):
    """Render a Matplotlib visualization as an inline FastHTML PNG image."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with _RENDER_LOCK:
            existing_figures = set(plt.get_fignums())

            try:
                figure = func(*args, **kwargs)
                if figure is None:
                    raise RuntimeError(
                        "A Matplotlib visualization must return its figure"
                    )

                with io.BytesIO() as image_buffer:
                    figure.savefig(image_buffer, format="png")
                    encoded_image = base64.b64encode(
                        image_buffer.getvalue()
                    ).decode("ascii")
            finally:
                created_figures = set(plt.get_fignums()) - existing_figures
                for figure_number in created_figures:
                    plt.close(figure_number)

        component = args[0]
        alt_text = getattr(
            component,
            "alt_text",
            "Data visualization",
        )
        summary_text = getattr(component, "summary_text", alt_text)
        return Div(
            Img(
                src=f"data:image/png;base64,{encoded_image}",
                alt=alt_text,
            ),
            P(summary_text, cls="visualization-summary"),
            cls="visualization",
        )

    return wrapper


class MatplotlibViz(BaseComponent):
    @matplotlib2fasthtml
    def build_component(self, entity_id, model):
        return self.visualization(entity_id, model)

    def visualization(self, entity_id, model):
        raise NotImplementedError

    def set_axis_styling(self, ax, bordercolor="white", fontcolor="white"):
        ax.title.set_color(fontcolor)
        ax.xaxis.label.set_color(fontcolor)
        ax.yaxis.label.set_color(fontcolor)

        ax.tick_params(color=bordercolor, labelcolor=fontcolor)
        for spine in ax.spines.values():
            spine.set_edgecolor(bordercolor)

        for line in ax.get_lines():
            line.set_linewidth(4)
            line.set_linestyle("dashdot")
