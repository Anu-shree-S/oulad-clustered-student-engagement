"""Central, filesystem-anchored path configuration for the TrackWise dashboard.

All locations are derived from this file's own location (never from the
current working directory), so the app resolves data correctly whether
Streamlit is launched from the project root or from inside oulad_dashboard/.

Layout on disk:
    oulad-clustered-student-engagement/    <- PROJECT_ROOT
        data/raw/                          <- RAW_DATA_DIR (original OULAD CSVs)
        oulad_dashboard/                   <- DASHBOARD_ROOT (this app)
            app.py
            data/                          <- DASHBOARD_DATA_DIR
                ml_Q*_test.parquet         <- BEHAVIOUR_DIR (behavioural tables)
                recommendations/           <- RECOMMENDATION_DIR
                predictions/               <- PREDICTION_DIR (optional, may be empty)
"""

from __future__ import annotations

from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DASHBOARD_ROOT.parent

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

DASHBOARD_DATA_DIR = DASHBOARD_ROOT / "data"

RECOMMENDATION_DIR = DASHBOARD_DATA_DIR / "recommendations"
PREDICTION_DIR = DASHBOARD_DATA_DIR / "predictions"

# The recommendation pipeline writes ml_Q*_test/train.parquet directly into
# DASHBOARD_DATA_DIR (alongside the "recommendations" and "predictions"
# subfolders), so behavioural tables share the same root.
BEHAVIOUR_DIR = DASHBOARD_DATA_DIR

REQUIRED_RAW_FILES = (
    "studentInfo.csv",
    "studentVle.csv",
    "studentAssessment.csv",
    "assessments.csv",
    "courses.csv",
    "vle.csv",
)


def validate_data_paths() -> dict:
    """Check known data locations and report what is available.

    Never raises: prediction output is optional, so its absence is reported,
    not treated as an error. Callers decide how to surface the result.
    """
    missing_raw_files = [
        name for name in REQUIRED_RAW_FILES
        if not (RAW_DATA_DIR / name).is_file()
    ]
    return {
        "raw_data_dir": RAW_DATA_DIR,
        "raw_data_dir_exists": RAW_DATA_DIR.exists(),
        "missing_raw_files": missing_raw_files,
        "recommendation_dir": RECOMMENDATION_DIR,
        "recommendation_dir_exists": RECOMMENDATION_DIR.exists(),
        "prediction_dir": PREDICTION_DIR,
        "prediction_dir_exists": PREDICTION_DIR.exists(),
        "prediction_files_present": PREDICTION_DIR.exists() and any(
            p.is_file() and p.name != ".gitkeep" for p in PREDICTION_DIR.iterdir()
        ),
    }
