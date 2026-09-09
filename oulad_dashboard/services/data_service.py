"""Shared cached CSV loading with explicit missing-data messages and no fake data."""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from config.paths import RAW_DATA_DIR
from services.privacy import build_student_display_map

REQUIRED_COLUMNS = {
    "studentInfo.csv": {"id_student", "code_module", "code_presentation", "final_result"},
    "studentVle.csv": {"id_student", "code_module", "code_presentation", "date", "sum_click"},
    "studentAssessment.csv": {"id_student", "id_assessment", "score"},
    "assessments.csv": {"id_assessment", "code_module", "code_presentation", "assessment_type", "date"},
    "courses.csv": {"code_module", "code_presentation", "module_presentation_length"},
}


class DataUnavailable(Exception):
    pass


def resolve_data_directory() -> Path:
    configured = os.environ.get("TRACKWISE_DATA_DIR")

    if configured:
        folder = Path(configured).expanduser().resolve()

        if not folder.is_dir():
            raise DataUnavailable(
                "The configured TrackWise data directory is unavailable. "
                "Check TRACKWISE_DATA_DIR."
            )

        return folder

    if (RAW_DATA_DIR / "studentInfo.csv").is_file():
        return RAW_DATA_DIR

    raise DataUnavailable(
        "studentInfo.csv could not be found.\n\n"
        f"Expected location:\n{RAW_DATA_DIR / 'studentInfo.csv'}\n\n"
        "Place the original OULAD CSVs there, or set the TRACKWISE_DATA_DIR "
        "environment variable to point at an alternate folder."
    )


@st.cache_data(show_spinner=False, max_entries=10)
def _read_csv(path: str, modified_ns: int, size: int):
    """Cache by file identity so replacing a CSV invalidates previous results."""
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, UnicodeError) as exc:
        raise DataUnavailable(f"{Path(path).name} could not be read. Check that it is an original OULAD CSV.") from exc
    missing = REQUIRED_COLUMNS.get(Path(path).name, set()) - set(frame.columns)
    if missing:
        raise DataUnavailable(f"{Path(path).name} is missing required columns: {', '.join(sorted(missing))}.")
    for column in ("id_student", "id_assessment", "date", "sum_click", "score", "is_banked"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "id_student" in frame.columns and frame["id_student"].isna().any():
        raise DataUnavailable(f"{Path(path).name} contains invalid learner keys. Check the original dataset.")
    if Path(path).name == "studentInfo.csv":
        if frame.empty:
            raise DataUnavailable("studentInfo.csv has no learner enrolments. Add a non-empty OULAD dataset.")
        if frame[["code_module", "code_presentation"]].isna().any().any():
            raise DataUnavailable("studentInfo.csv contains incomplete module/presentation assignments.")
    return frame


def load_csv(filename: str):
    """Load one named OULAD CSV, reporting expected file errors gracefully."""
    path = resolve_data_directory() / filename
    try:
        metadata = path.stat()
    except OSError as exc:
        raise DataUnavailable(f"{filename} could not be found.\n\nExpected location:\n{path}") from exc
    return _read_csv(str(path), metadata.st_mtime_ns, metadata.st_size)


def load_student_info():
    """Load enrolments for login and permission checks."""
    return load_csv("studentInfo.csv")


def load_dashboard_data():
    """Preserve the original dashboard tuple: info, VLE, scores, assessments."""
    # Check all four files before reading the large VLE file.
    folder = resolve_data_directory()
    names = ("studentInfo.csv", "studentVle.csv", "studentAssessment.csv", "assessments.csv")
    for name in names:
        if not (folder / name).is_file():
            raise DataUnavailable(f"{name} could not be found.\n\nExpected location:\n{folder / name}")
    return tuple(load_csv(name) for name in names)


def load_courses():
    """Load optional course lengths without introducing pipeline dependencies."""
    return load_csv("courses.csv")


def load_student_display_map():
    """Use the full dataset for aliases stable across roles, filters and reruns."""
    return build_student_display_map(load_student_info()["id_student"])
