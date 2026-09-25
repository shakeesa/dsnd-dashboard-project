from pathlib import Path

from setuptools import find_packages, setup

cwd = Path(__file__).resolve().parent
requirements_path = cwd / "employee_events" / "requirements.txt"
readme_path = cwd / "README.md"
requirements = [
    line.strip()
    for line in requirements_path.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]

setup_args = dict(
    name="employee_events",
    version="0.0",
    description="Read-only query API for employee performance events",
    long_description=readme_path.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    package_data={
        "employee_events": ["employee_events.db", "requirements.txt"]
    },
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.10",
)

if __name__ == "__main__":
    setup(**setup_args)
