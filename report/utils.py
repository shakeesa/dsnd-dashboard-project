import pickle
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
model_path = project_root / "assets" / "model.pkl"


def load_model():
    if not model_path.is_file():
        raise FileNotFoundError(f"Recruitment model not found: {model_path}")

    try:
        with model_path.open("rb") as model_file:
            return pickle.load(model_file)
    except (
        AttributeError,
        EOFError,
        ImportError,
        OSError,
        ValueError,
        pickle.PickleError,
    ) as error:
        message = f"Unable to load recruitment model from {model_path}"
        raise RuntimeError(message) from error
