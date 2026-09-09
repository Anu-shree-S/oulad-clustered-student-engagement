"""Deployment-safe data loading for TrackWise.

The hosted Streamlit app reads compact Parquet exports produced by the
recommendation pipeline. Raw OULAD CSVs remain an optional local fallback.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from config.paths import DASHBOARD_DATA_DIR, RAW_DATA_DIR
from services.privacy import build_student_display_map


PROCESSED_FILES = {
    "student_info": DASHBOARD_DATA_DIR / "dashboard_student_context.parquet",
    "student_vle": DASHBOARD_DATA_DIR / "dashboard_weekly_vle.parquet",
    "student_assessment": DASHBOARD_DATA_DIR / "dashboard_student_assessment.parquet",
    "assessments": DASHBOARD_DATA_DIR / "dashboard_assessments.parquet",
    "courses": DASHBOARD_DATA_DIR / "dashboard_courses.parquet",
}

PROCESSED_REQUIRED_COLUMNS = {
    "student_info": {"id_student", "code_module", "code_presentation", "final_result"},
    "student_vle": {
        "id_student", "code_module", "code_presentation",
        "date", "sum_click", "activity_type",
    },
    "student_assessment": {"id_student", "id_assessment", "score", "date_submitted"},
    "assessments": {
        "id_assessment", "code_module", "code_presentation",
        "assessment_type", "date",
    },
    "courses": {"code_module", "code_presentation"},
}

RAW_REQUIRED_COLUMNS = {
    "studentInfo.csv": {"id_student", "code_module", "code_presentation", "final_result"},
    "studentVle.csv": {"id_student", "code_module", "code_presentation", "date", "sum_click"},
    "studentAssessment.csv": {"id_student", "id_assessment", "score"},
    "assessments.csv": {"id_assessment", "code_module", "code_presentation", "assessment_type", "date"},
    "courses.csv": {"code_module", "code_presentation", "module_presentation_length"},
}


class DataUnavailable(Exception):
    pass


def _normalise_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in (
        "id_student", "id_assessment", "date", "date_submitted",
        "sum_click", "score", "is_banked", "weight",
        "module_presentation_length",
    ):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


@st.cache_data(show_spinner=False, max_entries=20)
def _read_parquet(path: str, modified_ns: int, size: int, dataset_key: str):
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:
        raise DataUnavailable(
            f"{Path(path).name} could not be read. "
            "Re-run the recommendation pipeline export."
        ) from exc

    missing = PROCESSED_REQUIRED_COLUMNS.get(dataset_key, set()) - set(frame.columns)
    if missing:
        raise DataUnavailable(
            f"{Path(path).name} is missing required columns: "
            f"{', '.join(sorted(missing))}."
        )

    frame = _normalise_numeric(frame)
    if "id_student" in frame.columns and frame["id_student"].isna().any():
        raise DataUnavailable(f"{Path(path).name} contains invalid learner keys.")
    return frame


def _load_processed(dataset_key: str) -> pd.DataFrame:
    path = PROCESSED_FILES[dataset_key]
    try:
        metadata = path.stat()
    except OSError as exc:
        raise DataUnavailable(
            f"{path.name} could not be found.\n\n"
            f"Expected location:\n{path}\n\n"
            "Run the final export cell in recommendation-pipeline.ipynb "
            "and commit the generated Parquet files."
        ) from exc
    return _read_parquet(str(path), metadata.st_mtime_ns, metadata.st_size, dataset_key)


def _processed_dashboard_available() -> bool:
    required = (
        "student_info", "student_vle", "student_assessment", "assessments"
    )
    return all(PROCESSED_FILES[key].is_file() for key in required)


# ---------------------------------------------------------------------
# Optional raw-CSV fallback for local development
# ---------------------------------------------------------------------

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
        "Processed dashboard files are unavailable and no local raw OULAD "
        "dataset was found.\n\n"
        f"Processed files are expected under:\n{DASHBOARD_DATA_DIR}\n\n"
        "Run the recommendation pipeline export and push the generated "
        "dashboard Parquet files to GitHub."
    )


@st.cache_data(show_spinner=False, max_entries=10)
def _read_csv(path: str, modified_ns: int, size: int):
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, UnicodeError) as exc:
        raise DataUnavailable(
            f"{Path(path).name} could not be read. "
            "Check that it is an original OULAD CSV."
        ) from exc

    missing = RAW_REQUIRED_COLUMNS.get(Path(path).name, set()) - set(frame.columns)
    if missing:
        raise DataUnavailable(
            f"{Path(path).name} is missing required columns: "
            f"{', '.join(sorted(missing))}."
        )
    return _normalise_numeric(frame)


def load_csv(filename: str):
    path = resolve_data_directory() / filename
    try:
        metadata = path.stat()
    except OSError as exc:
        raise DataUnavailable(
            f"{filename} could not be found.\n\nExpected location:\n{path}"
        ) from exc
    return _read_csv(str(path), metadata.st_mtime_ns, metadata.st_size)


# ---------------------------------------------------------------------
# Public API used by the dashboard
# ---------------------------------------------------------------------

def load_student_info():
    """Load learner enrolments for login and permission checks."""
    if PROCESSED_FILES["student_info"].is_file():
        frame = _load_processed("student_info")
        if frame.empty:
            raise DataUnavailable(
                "dashboard_student_context.parquet has no learner enrolments."
            )
        return frame
    return load_csv("studentInfo.csv")


def load_dashboard_data():
    """Return the original four-table tuple used throughout the dashboard.

    Order is intentionally preserved:
        studentInfo, studentVle, studentAssessment, assessments
    """
    if _processed_dashboard_available():
        return (
            _load_processed("student_info"),
            _load_processed("student_vle"),
            _load_processed("student_assessment"),
            _load_processed("assessments"),
        )

    names = (
        "studentInfo.csv",
        "studentVle.csv",
        "studentAssessment.csv",
        "assessments.csv",
    )
    return tuple(load_csv(name) for name in names)


def load_courses():
    """Load compact course metadata when available, otherwise raw courses.csv."""
    if PROCESSED_FILES["courses"].is_file():
        return _load_processed("courses")
    return load_csv("courses.csv")


def load_student_display_map():
    """Use the full learner list for aliases stable across roles and reruns."""
    return build_student_display_map(load_student_info()["id_student"])
