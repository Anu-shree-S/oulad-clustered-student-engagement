"""Dashboard-facing learning analytics helpers.

The dashboard consumes precomputed recommendation/behaviour artefacts when present.
Prediction output is optional and is deliberately kept separate from behavioural
recommendations so the UI can be developed before model exports are available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st

from config.paths import BEHAVIOUR_DIR, PREDICTION_DIR, RECOMMENDATION_DIR
from services.data_service import DataUnavailable, load_dashboard_data, load_student_info
from services.privacy import build_student_display_map

# Q1-Q4 are retained for the existing dashboard pages.  The prediction model
# currently exports Q1, Q2, Q3 and a full-course ``master`` checkpoint.
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
PREDICTION_CHECKPOINTS = ["Q1", "Q2", "Q3", "master"]
QUARTER_LABELS = {
    "Q1": "Q1 · Early",
    "Q2": "Q2 · Main checkpoint",
    "Q3": "Q3 · Refinement",
    "Q4": "Q4 · Late stage",
    "master": "Final · Full course",
}
QUARTER_WEEK_END = {"Q1": 9, "Q2": 19, "Q3": 29, "Q4": 10_000, "master": 10_000}

PREDICTION_KEYS = ["id_student", "code_module", "code_presentation", "quarter"]
PREDICTION_VALUE_COLS = [
    "risk_probability",
    "predicted_class",
    "threshold",
    "model_name",
]

STUDENT_FEATURES = [
    ("study_consistency", "Study Consistency", ["active_weeks_ratio_{q}", "active_weeks_ratio_norm"], True),
    ("study_spacing", "Study Spacing", ["spacing_score_{q}", "spacing_score_full"], True),
    ("study_timing", "Study Timing", ["AP_{q}", "AP_full"], True),
    ("course_materials", "Course Materials", ["norm_content_{q}", "content_norm_{q}", "content_ratio_{q}", "content_ratio_norm"], True),
    ("assessment_engagement", "Practice & Assessments", ["norm_assessment_{q}", "assessment_norm_{q}", "assessment_ratio_{q}", "assessment_ratio_norm"], True),
    ("social_engagement", "Learning With Others", ["norm_social_{q}", "social_norm_{q}", "social_ratio_{q}", "social_ratio_norm"], True),
    ("overall_engagement", "Overall Engagement", ["norm_total_{q}", "total_engagement_{q}", "norm_total"], True),
    ("learning_balance", "Learning Balance", ["dim_entropy_norm_{q}", "entropy_norm_{q}", "dim_entropy_norm"], True),
    ("deadline_adherence", "Deadline Adherence", ["num_late_submissions_{q}", "num_late_submissions"], False),
]

ISSUE_LIBRARY = {
    "Late assessment preparation": {
        "title": "Give yourself an earlier start",
        "why": "Your assessment activity is concentrated closer to deadlines than the historical successful-peer benchmark.",
        "action": "Choose the next assessment and set a personal start date several days before the deadline.",
        "category": "Assessment behaviour",
    },
    "Frequent late submissions": {
        "title": "Plan around upcoming deadlines",
        "why": "Your recent submission pattern shows more deadline pressure than the successful-peer reference group.",
        "action": "Add every upcoming deadline to your planner and aim to finish the first draft one day early.",
        "category": "Assessment behaviour",
    },
    "Low assessment practice": {
        "title": "Use practice activities more regularly",
        "why": "Practice and assessment engagement is below the successful-peer benchmark for learners with a similar behavioural profile.",
        "action": "Complete one available quiz or self-test before your next graded assessment.",
        "category": "Assessment behaviour",
    },
    "Low engagement with course materials": {
        "title": "Reconnect with key course materials",
        "why": "Your use of course materials is below the successful-peer benchmark for this learning context.",
        "action": "Revisit the key reading, page or resource linked to your next assessment topic.",
        "category": "Course materials",
    },
    "Irregular study pattern": {
        "title": "Spread your study across the week",
        "why": "Your activity is more concentrated into bursts than the successful-peer reference pattern.",
        "action": "Plan three shorter study sessions across different days this week.",
        "category": "Study routine",
    },
    "Low study consistency": {
        "title": "Build a steadier weekly routine",
        "why": "You have been active in fewer course weeks than the successful-peer reference group.",
        "action": "Set a recurring reminder to check the course three times this week, even for short sessions.",
        "category": "Study routine",
    },
    "Low participation in discussions": {
        "title": "Connect with your learning community",
        "why": "Your collaborative activity is lower than the successful-peer benchmark in this course context.",
        "action": "Read the current discussion and contribute one question, reply or useful resource this week.",
        "category": "Participation",
    },
}


@st.cache_data(show_spinner=False, max_entries=40)
def _read_table(path: str, modified_ns: int, size: int) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower() == ".json":
        return pd.read_json(p)
    return pd.read_csv(p)


def _load_path(path: Path | None) -> pd.DataFrame:
    if path is None or not path.is_file():
        return pd.DataFrame()
    stat = path.stat()
    return _read_table(str(path), stat.st_mtime_ns, stat.st_size)


def _canonical_quarter(quarter: str | None) -> str:
    """Normalise UI/checkpoint aliases without pretending Q4 is Master."""
    text = str(quarter or "").strip()
    upper = text.upper()
    if upper in {"MASTER", "FINAL", "FULL", "FULL COURSE", "FULL_COURSE"}:
        return "master"
    if upper in {"Q1", "Q2", "Q3", "Q4"}:
        return upper
    return text


def _data_roots() -> list[Path]:
    """Return plausible dashboard data roots, de-duplicated in priority order."""
    candidates = [
        PREDICTION_DIR,
        PREDICTION_DIR.parent,
        RECOMMENDATION_DIR.parent,
        BEHAVIOUR_DIR,
        BEHAVIOUR_DIR.parent,
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        p = Path(candidate)
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            roots.append(p)
            seen.add(key)
    return roots


def load_recommendation_summary(quarter: str) -> pd.DataFrame:
    q = _canonical_quarter(quarter)
    return _load_path(RECOMMENDATION_DIR / f"recommendation_summary_{q}.parquet")


def load_recommendation_details(quarter: str) -> pd.DataFrame:
    q = _canonical_quarter(quarter)
    return _load_path(RECOMMENDATION_DIR / f"recommendation_details_{q}.parquet")


def load_cluster_profiles(quarter: str) -> pd.DataFrame:
    q = _canonical_quarter(quarter)
    return _load_path(RECOMMENDATION_DIR / f"cluster_profiles_{q}.json")


def load_quarter_comparison() -> pd.DataFrame:
    return _load_path(RECOMMENDATION_DIR / "recommendation_quarter_comparison.csv")


def load_behaviour_table(quarter: str, cohort: str = "test") -> pd.DataFrame:
    q = _canonical_quarter(quarter)
    cohort = "train" if cohort == "train" else "test"
    return _load_path(BEHAVIOUR_DIR / f"ml_{q}_{cohort}.parquet")


def _prediction_candidates() -> Iterable[Path]:
    """Yield canonical prediction exports before any legacy/fallback filenames."""
    names = [
        "dashboard_student_predictions.parquet",
        "dashboard_student_predictions.csv",
        "student_predictions.parquet",
        "student_predictions.csv",
        "dashboard_predictions.parquet",
        "dashboard_predictions.csv",
        # The integrated file is a safe fallback because it preserves the
        # prediction pipeline's canonical probability/class/model fields.
        "dashboard_student_quarter.parquet",
        "dashboard_student_quarter.csv",
    ]
    seen: set[str] = set()
    for root in _data_roots():
        for name in names:
            path = root / name
            key = str(path)
            if key not in seen:
                seen.add(key)
                yield path

    # Legacy discovery remains last and only valid prediction-shaped files are
    # accepted by ``load_prediction_data`` below.
    for root in _data_roots():
        if root.is_dir():
            for pattern in ("*prediction*.parquet", "*prediction*.csv"):
                for path in sorted(root.glob(pattern)):
                    key = str(path)
                    if key not in seen:
                        seen.add(key)
                        yield path


def _normalise_prediction_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    required = set(PREDICTION_KEYS + PREDICTION_VALUE_COLS)
    if not required.issubset(df.columns):
        return pd.DataFrame()

    out = df.copy()
    out["quarter"] = out["quarter"].map(_canonical_quarter)
    out["id_student"] = pd.to_numeric(out["id_student"], errors="coerce").astype("Int64")
    out["risk_probability"] = pd.to_numeric(out["risk_probability"], errors="coerce")
    out["predicted_class"] = pd.to_numeric(out["predicted_class"], errors="coerce").astype("Int64")
    out["threshold"] = pd.to_numeric(out["threshold"], errors="coerce")
    out = out.dropna(subset=["id_student"]).copy()

    # Keep one canonical model result per enrolment/checkpoint.  The backend
    # verification guarantees uniqueness for the primary export; this also
    # protects the dashboard if a fallback file contains duplicate rows.
    out = out.drop_duplicates(PREDICTION_KEYS, keep="first")
    return out


def load_prediction_data() -> pd.DataFrame:
    for path in _prediction_candidates():
        if not path.is_file():
            continue
        frame = _normalise_prediction_frame(_load_path(path))
        if not frame.empty:
            return frame
    return pd.DataFrame()


def _prediction_slice(quarter: str) -> pd.DataFrame:
    """Return predictions for the exact requested checkpoint only."""
    q = _canonical_quarter(quarter)
    df = load_prediction_data()
    if df.empty or "quarter" not in df.columns:
        return pd.DataFrame()
    return df[df["quarter"].eq(q)].copy()


def load_dashboard_student_quarter() -> pd.DataFrame:
    """Load the integrated deployment table generated by the recommender."""
    for root in _data_roots():
        for name in ("dashboard_student_quarter.parquet", "dashboard_student_quarter.csv"):
            path = root / name
            if path.is_file():
                return _load_path(path)
    return pd.DataFrame()


def analytics_status(quarter: str) -> dict:
    # Prediction status is checkpoint-specific.  Q4 correctly reports False
    # until a genuine Q4 model export exists; it never falls back to Q1/Q2/Q3.
    return {
        "recommendations": not load_recommendation_summary(quarter).empty,
        "behaviour": not load_behaviour_table(quarter).empty,
        "predictions": not _prediction_slice(quarter).empty,
    }


def _filter_enrolment(df: pd.DataFrame, student_id: int, module: str, presentation: str) -> pd.DataFrame:
    if df.empty:
        return df
    required = {"id_student", "code_module", "code_presentation"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    return df[
        (pd.to_numeric(df["id_student"], errors="coerce") == int(student_id))
        & (df["code_module"].astype(str) == str(module))
        & (df["code_presentation"].astype(str) == str(presentation))
    ]


def student_recommendation_row(student_id: int, module: str, presentation: str, quarter: str) -> dict:
    frame = _filter_enrolment(load_recommendation_summary(quarter), student_id, module, presentation)
    return {} if frame.empty else frame.iloc[0].to_dict()


def student_recommendations(student_id: int, module: str, presentation: str, quarter: str, limit: int = 3) -> list[dict]:
    details = _filter_enrolment(load_recommendation_details(quarter), student_id, module, presentation)
    if details.empty:
        return []
    sort_cols = [c for c in ["priority", "weighted_severity", "gap_severity"] if c in details.columns]
    if sort_cols:
        ascending = [True if c == "priority" else False for c in sort_cols]
        details = details.sort_values(sort_cols, ascending=ascending)
    records = []
    seen_categories = set()
    for _, row in details.iterrows():
        issue = str(row.get("issue_label") or "")
        card = ISSUE_LIBRARY.get(issue, {
            "title": issue or "Focus on this learning habit",
            "why": "This learning habit is below the historical successful-peer benchmark for your current context.",
            "action": "Choose one small action you can complete this week to strengthen this area.",
            "category": str(row.get("area") or "Study behaviour"),
        })
        category = str(row.get("category") or card["category"])
        if category in seen_categories:
            continue
        seen_categories.add(category)
        records.append({
            "issue": issue,
            "title": card["title"],
            "why": card["why"],
            "action": card["action"],
            "category": card["category"],
            "severity": float(row.get("gap_severity", 0) or 0),
            "priority": int(row.get("priority", len(records) + 1) or len(records) + 1),
        })
        if len(records) >= limit:
            break
    return records


def _first_present(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    cols = set(columns)
    for name in candidates:
        if name in cols:
            return name
    return None


def _feature_column(df: pd.DataFrame, templates: list[str], quarter: str) -> str | None:
    candidates = []
    for template in templates:
        candidates.append(template.format(q=quarter))
    return _first_present(df.columns, candidates)


def _defined_mask(df: pd.DataFrame, key: str, quarter: str) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if key == "study_timing":
        missing_col = _first_present(df.columns, [f"AP_{quarter}_missing", "AP_missing"])
        n_col = _first_present(df.columns, [f"n_submissions_{quarter}", f"num_submissions_{quarter}", "n_submissions"])
        if missing_col:
            mask &= pd.to_numeric(df[missing_col], errors="coerce").fillna(1).eq(0)
        if n_col:
            mask &= pd.to_numeric(df[n_col], errors="coerce").fillna(0).gt(0)
    if key == "study_spacing":
        defined_col = _first_present(df.columns, [f"spacing_defined_{quarter}", "spacing_defined"])
        if defined_col:
            mask &= pd.to_numeric(df[defined_col], errors="coerce").fillna(0).gt(0)
    return mask


def _peer_reference(df: pd.DataFrame, row: pd.Series, key: str, value_col: str, quarter: str) -> pd.Series:
    peer = df.copy()
    if "code_module" in peer.columns and "code_module" in row.index:
        same_module = peer[peer["code_module"].astype(str) == str(row["code_module"])]
        if len(same_module) >= 20:
            peer = same_module
    if "target_at_risk" in peer.columns:
        successful = peer[pd.to_numeric(peer["target_at_risk"], errors="coerce").fillna(1).eq(0)]
        if len(successful) >= 20:
            peer = successful
    peer = peer[_defined_mask(peer, key, quarter)]
    values = pd.to_numeric(peer[value_col], errors="coerce").dropna()
    return values


def _relative_status(value: float, peers: pd.Series, higher_better: bool) -> tuple[str, float | None]:
    if peers.empty or not np.isfinite(value):
        return "Observed", None
    median = float(peers.median())
    q1, q3 = float(peers.quantile(0.25)), float(peers.quantile(0.75))
    iqr = max(q3 - q1, 0.08 if abs(median) <= 2 else 1.0)
    signed = (value - median) / iqr if higher_better else (median - value) / iqr
    if signed >= 0.75:
        status = "Strong"
    elif signed >= -0.35:
        status = "Steady"
    elif signed >= -1.0:
        status = "Building"
    else:
        status = "Opportunity"
    return status, round(float(signed), 2)


def student_behaviour_tiles(student_id: int, module: str, presentation: str, quarter: str) -> list[dict]:
    df = load_behaviour_table(quarter)
    student = _filter_enrolment(df, student_id, module, presentation)
    if student.empty:
        return []
    row = student.iloc[0]
    tiles = []
    for key, label, templates, higher_better in STUDENT_FEATURES:
        col = _feature_column(df, templates, quarter)
        if not col:
            continue
        if not bool(_defined_mask(student, key, quarter).iloc[0]):
            continue
        value = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        peers = _peer_reference(df, row, key, col, quarter)
        status, relative = _relative_status(float(value), peers, higher_better)
        display_value = float(value)
        if key == "deadline_adherence":
            value_text = f"{display_value:.0f} late"
        elif abs(display_value) <= 1.25:
            value_text = f"{display_value * 100:.0f}%"
        else:
            value_text = f"{display_value:.2f}"
        tiles.append({
            "key": key,
            "label": label,
            "status": status,
            "relative": relative,
            "value": display_value,
            "value_text": value_text,
        })
    return tiles


def student_strengths_opportunities(tiles: list[dict]) -> tuple[list[str], list[str]]:
    strengths = [t["label"] for t in tiles if t["status"] in {"Strong", "Steady"}][:3]
    opportunities = [t["label"] for t in tiles if t["status"] in {"Building", "Opportunity"}][:3]
    return strengths, opportunities


def student_learning_pattern(student_id: int, module: str, presentation: str, quarter: str) -> dict:
    summary = student_recommendation_row(student_id, module, presentation, quarter)
    label = summary.get("learning_pattern") if summary else None
    cluster_id = summary.get("cluster_id") if summary else None
    profiles = load_cluster_profiles(quarter)
    if label:
        match = profiles[profiles["label"].astype(str) == str(label)] if not profiles.empty and "label" in profiles.columns else pd.DataFrame()
        row = match.iloc[0].to_dict() if not match.empty else {}
        return {"label": str(label), "summary": str(row.get("summary") or "A descriptive pattern based on your current behavioural features."), "cluster_id": cluster_id}
    return {"label": "Current learning pattern", "summary": "A behavioural profile will appear here when recommendation exports are available.", "cluster_id": cluster_id}


def student_learning_mix(student_id: int, module: str, presentation: str, quarter: str) -> list[dict]:
    df = load_behaviour_table(quarter)
    student = _filter_enrolment(df, student_id, module, presentation)
    if student.empty:
        return []
    row = student.iloc[0]
    specs = [
        ("Course materials", [f"content_ratio_{quarter}", "content_ratio_norm"]),
        ("Practice & assessments", [f"assessment_ratio_{quarter}", "assessment_ratio_norm"]),
        ("Learning with others", [f"social_ratio_{quarter}", "social_ratio_norm"]),
    ]
    vals = []
    for label, candidates in specs:
        col = _first_present(df.columns, candidates)
        if not col:
            continue
        value = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
        if pd.notna(value) and float(value) >= 0:
            vals.append((label, float(value)))
    total = sum(v for _, v in vals)
    if total <= 0:
        return []
    return [{"label": label, "percentage": round(100 * value / total, 1)} for label, value in vals]


def student_behaviour_trend(student_id: int, module: str, presentation: str, upto_quarter: str) -> list[dict]:
    checkpoint = _canonical_quarter(upto_quarter)
    timeline = ["Q1", "Q2", "Q3", "master"] if checkpoint == "master" else QUARTERS
    if checkpoint not in timeline:
        return []
    q_index = timeline.index(checkpoint)
    history: dict[str, list[tuple[str, str]]] = {}
    for q in timeline[:q_index + 1]:
        for tile in student_behaviour_tiles(student_id, module, presentation, q):
            history.setdefault(tile["label"], []).append((q, tile["status"]))
    rank = {"Opportunity": 0, "Building": 1, "Observed": 1, "Steady": 2, "Strong": 3}
    out = []
    for label, vals in history.items():
        direction = "Steady"
        if len(vals) >= 2:
            diff = rank.get(vals[-1][1], 1) - rank.get(vals[-2][1], 1)
            direction = "Improving" if diff > 0 else "Needs focus" if diff < 0 else "Steady"
        out.append({"label": label, "history": vals, "direction": direction})
    return out


def prediction_for_student(student_id: int, module: str, presentation: str, quarter: str) -> dict:
    """Return the saved model output for one exact learner/checkpoint."""
    frame = _filter_enrolment(
        _prediction_slice(quarter),
        student_id,
        module,
        presentation,
    )
    if frame.empty:
        return {}

    row = frame.iloc[0]
    probability = pd.to_numeric(
        pd.Series([row.get("risk_probability")]), errors="coerce"
    ).iloc[0]
    predicted_class = pd.to_numeric(
        pd.Series([row.get("predicted_class")]), errors="coerce"
    ).iloc[0]
    threshold = pd.to_numeric(
        pd.Series([row.get("threshold")]), errors="coerce"
    ).iloc[0]

    probability_value = None if pd.isna(probability) else float(probability)
    class_value = None if pd.isna(predicted_class) else int(predicted_class)
    threshold_value = None if pd.isna(threshold) else float(threshold)
    status = (
        "Flagged for Attention" if class_value == 1
        else "Not Flagged" if class_value == 0
        else None
    )

    return {
        # ``probability`` is retained for compatibility with the current pages.
        "probability": probability_value,
        "risk_probability": probability_value,
        "predicted_class": class_value,
        "prediction_status": status,
        "risk_label": status,
        "model_name": row.get("model_name"),
        "threshold": threshold_value,
        "checkpoint": _canonical_quarter(quarter),
        "available": probability_value is not None,
    }


def weekly_activity(student_id: int, module: str, presentation: str, quarter: str) -> pd.DataFrame:
    _, vle, _, _ = load_dashboard_data()
    data = vle[(vle["code_module"] == module) & (vle["code_presentation"] == presentation)].copy()
    if data.empty:
        return pd.DataFrame()
    data["week"] = (pd.to_numeric(data["date"], errors="coerce").fillna(0).clip(lower=0) // 7 + 1).astype(int)
    data = data[data["week"] <= QUARTER_WEEK_END[quarter]]
    me = data[data["id_student"] == student_id].groupby("week")["sum_click"].sum().rename("My activity")
    cohort = data.groupby(["id_student", "week"])["sum_click"].sum().groupby("week").mean().rename("Cohort average")
    return pd.concat([me, cohort], axis=1).fillna(0).reset_index()


def assessment_progress(student_id: int, module: str, presentation: str, quarter: str) -> pd.DataFrame:
    _, _, sa, ass = load_dashboard_data()
    ass = ass[(ass["code_module"] == module) & (ass["code_presentation"] == presentation) & (ass["assessment_type"] != "Exam")].copy()
    end_day = QUARTER_WEEK_END[quarter] * 7
    if end_day < 70_000:
        ass = ass[pd.to_numeric(ass["date"], errors="coerce").fillna(end_day + 1) <= end_day]
    frame = sa[sa["id_student"] == student_id].merge(ass[["id_assessment", "date", "assessment_type"]], on="id_assessment", how="inner")
    if frame.empty:
        return frame
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame = frame.sort_values("date")
    frame["Task"] = [f"Task {i + 1}" for i in range(len(frame))]
    return frame[["Task", "assessment_type", "score", "date"]]


def _attach_prediction_context(frame: pd.DataFrame, quarter: str) -> pd.DataFrame:
    """Fill prediction context into recommendation rows without changing support fields."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()

    out = frame.copy()
    pred = _prediction_slice(quarter)
    if pred.empty:
        if "prediction_available" not in out.columns:
            out["prediction_available"] = False
        return out

    keys = ["id_student", "code_module", "code_presentation"]
    if not set(keys).issubset(out.columns):
        return out

    pred_cols = keys + [
        "risk_probability",
        "predicted_class",
        "threshold",
        "model_name",
    ]
    pred = pred[pred_cols].drop_duplicates(keys)

    merged = out.merge(pred, on=keys, how="left", validate="one_to_one", suffixes=("", "__pred"))
    for col in ["risk_probability", "predicted_class", "threshold", "model_name"]:
        fallback = f"{col}__pred"
        if fallback not in merged.columns:
            continue
        if col in out.columns:
            merged[col] = merged[col].where(merged[col].notna(), merged[fallback])
        else:
            merged[col] = merged[fallback]
        merged.drop(columns=fallback, inplace=True)

    probability = pd.to_numeric(merged.get("risk_probability"), errors="coerce")
    classes = pd.to_numeric(merged.get("predicted_class"), errors="coerce")
    merged["prediction_available"] = probability.notna()
    if "prediction_status" not in merged.columns:
        merged["prediction_status"] = np.where(
            classes.eq(1), "Flagged for Attention",
            np.where(classes.eq(0), "Not Flagged", None),
        )
    if "prediction_threshold" not in merged.columns and "threshold" in merged.columns:
        merged["prediction_threshold"] = merged["threshold"]
    if "prediction_model" not in merged.columns and "model_name" in merged.columns:
        merged["prediction_model"] = merged["model_name"]
    return merged


def cohort_summary(module: str, presentation: str, quarter: str) -> pd.DataFrame:
    summary = load_recommendation_summary(quarter)
    if summary.empty:
        return summary
    summary = summary[
        (summary["code_module"].astype(str) == str(module))
        & (summary["code_presentation"].astype(str) == str(presentation))
    ].copy()
    return _attach_prediction_context(summary, quarter)


def prediction_overview(
    quarter: str,
    module: str | None = None,
    presentation: str | None = None,
) -> dict:
    """Aggregate model coverage/risk for Instructor and Admin dashboard cards."""
    pred = _prediction_slice(quarter)
    if module is not None and not pred.empty:
        pred = pred[pred["code_module"].astype(str).eq(str(module))]
    if presentation is not None and not pred.empty:
        pred = pred[pred["code_presentation"].astype(str).eq(str(presentation))]

    summary = load_recommendation_summary(quarter)
    if module is not None and not summary.empty:
        summary = summary[summary["code_module"].astype(str).eq(str(module))]
    if presentation is not None and not summary.empty:
        summary = summary[summary["code_presentation"].astype(str).eq(str(presentation))]

    denominator = int(len(summary)) if not summary.empty else int(len(pred))
    n_predictions = int(len(pred))
    if pred.empty:
        return {
            "n_students": denominator,
            "n_predictions": 0,
            "prediction_coverage_pct": 0.0,
            "n_model_flagged": 0,
            "pct_model_flagged": None,
            "mean_risk_probability": None,
        }

    classes = pd.to_numeric(pred["predicted_class"], errors="coerce")
    probs = pd.to_numeric(pred["risk_probability"], errors="coerce")
    return {
        "n_students": denominator,
        "n_predictions": n_predictions,
        "prediction_coverage_pct": round(100 * n_predictions / max(denominator, 1), 1),
        "n_model_flagged": int(classes.eq(1).sum()),
        "pct_model_flagged": round(100 * float(classes.eq(1).mean()), 1),
        "mean_risk_probability": round(float(probs.mean()), 4) if probs.notna().any() else None,
    }


def cohort_details(module: str, presentation: str, quarter: str) -> pd.DataFrame:
    details = load_recommendation_details(quarter)
    if details.empty:
        return details
    return details[(details["code_module"].astype(str) == str(module)) & (details["code_presentation"].astype(str) == str(presentation))].copy()


def cohort_priority_table(module: str, presentation: str, quarter: str) -> pd.DataFrame:
    """Instructor queue: prediction prioritises review; behaviour defines support."""
    summary = cohort_summary(module, presentation, quarter)
    if summary.empty:
        return summary
    details = cohort_details(module, presentation, quarter)
    mapping = build_student_display_map(load_student_info()["id_student"])
    out = summary.copy()
    out["Learner"] = pd.to_numeric(out["id_student"], errors="coerce").map(mapping)

    if not details.empty:
        ranked = details.sort_values([c for c in ["id_student", "priority"] if c in details.columns])
        top1 = (
            ranked.groupby("id_student").nth(0).reset_index()[["id_student", "issue_label"]]
            .rename(columns={"issue_label": "Main opportunity"})
        )
        top2 = (
            ranked.groupby("id_student").nth(1).reset_index()[["id_student", "issue_label"]]
            .rename(columns={"issue_label": "Second opportunity"})
        )
        out = out.merge(top1, on="id_student", how="left").merge(top2, on="id_student", how="left")

    if "risk_probability" in out.columns:
        out["Model probability"] = pd.to_numeric(out["risk_probability"], errors="coerce")
    if "predicted_class" in out.columns:
        cls = pd.to_numeric(out["predicted_class"], errors="coerce")
        out["Model flag"] = np.where(
            cls.eq(1), "Flagged",
            np.where(cls.eq(0), "Not Flagged", "Unavailable"),
        )
    if "prediction_status" in out.columns:
        out["Prediction status"] = out["prediction_status"]

    # Transparent operational ordering:
    # 1) model flag, 2) model probability, 3) behavioural intervention intensity,
    # 4) behavioural gap severity.  None of these fields rewrites the recommendation.
    out["_model_flag_rank"] = pd.to_numeric(out.get("predicted_class"), errors="coerce").fillna(-1)
    out["_model_probability_rank"] = pd.to_numeric(out.get("risk_probability"), errors="coerce").fillna(-1)
    intervention_rank = {
        "Instructor Follow-up": 4,
        "Targeted Support": 3,
        "Self-Guided Support": 2,
        "No Additional Action": 1,
    }
    out["_intervention_rank"] = out.get(
        "intervention_level", pd.Series(index=out.index, dtype=object)
    ).map(intervention_rank).fillna(0)
    out["_severity_rank"] = pd.to_numeric(out.get("max_gap_severity"), errors="coerce").fillna(0)
    out = out.sort_values(
        ["_model_flag_rank", "_model_probability_rank", "_intervention_rank", "_severity_rank"],
        ascending=[False, False, False, False],
    )

    order = [
        "Learner",
        "Prediction status",
        "Model flag",
        "Model probability",
        "instructor_support_status",
        "intervention_level",
        "learning_pattern",
        "Main opportunity",
        "Second opportunity",
        "max_gap_severity",
        "predicted_class",
        "risk_probability",
        "prediction_model",
        "prediction_threshold",
        "id_student",
    ]
    cols = [c for c in order if c in out.columns]
    return out[cols]


def common_issues(module, presentation, quarter: str) -> pd.DataFrame:
    details = load_recommendation_details(quarter)
    if details.empty:
        return details
    if module is not None:
        if isinstance(module, (list, tuple, set)):
            details = details[details["code_module"].astype(str).isin([str(x) for x in module])]
        else:
            details = details[details["code_module"].astype(str) == str(module)]
    if presentation is not None:
        if isinstance(presentation, (list, tuple, set)):
            details = details[details["code_presentation"].astype(str).isin([str(x) for x in presentation])]
        else:
            details = details[details["code_presentation"].astype(str) == str(presentation)]
    if details.empty:
        return pd.DataFrame()
    grouped = details.groupby(["issue_label", "area"], dropna=False).agg(
        Students=("id_student", "nunique"),
        AvgSeverity=("gap_severity", "mean"),
    ).reset_index()
    denom = max(details["id_student"].nunique(), 1)
    grouped["Prevalence"] = 100 * grouped["Students"] / denom
    grouped["Teaching opportunity"] = np.select(
        [grouped["Prevalence"] >= 25, grouped["Prevalence"] >= 10],
        ["Cohort-wide opportunity", "Targeted group opportunity"],
        default="Primarily individual",
    )
    return grouped.sort_values(["Students", "AvgSeverity"], ascending=False)


def module_support_summary(quarter: str, modules: list[str] | None = None, presentations: list[str] | None = None) -> pd.DataFrame:
    summary = load_recommendation_summary(quarter)
    if summary.empty:
        return summary
    if modules:
        summary = summary[summary["code_module"].isin(modules)]
    if presentations:
        summary = summary[summary["code_presentation"].isin(presentations)]
    if summary.empty:
        return pd.DataFrame()
    summary = _attach_prediction_context(summary, quarter)
    grouped = summary.groupby("code_module").agg(
        Students=("id_student", "nunique"),
        AvgRecommendations=("n_recs", "mean"),
        AvgSeverity=("max_gap_severity", "mean"),
        FollowUp=("intervention_level", lambda s: int((s == "Instructor Follow-up").sum())),
        Targeted=("intervention_level", lambda s: int((s == "Targeted Support").sum())),
        SelfGuided=("intervention_level", lambda s: int((s == "Self-Guided Support").sum())),
        NoAction=("intervention_level", lambda s: int((s == "No Additional Action").sum())),
        Predictions=("prediction_available", lambda s: int(pd.Series(s).fillna(False).astype(bool).sum())),
        ModelFlagged=("predicted_class", lambda s: int(pd.to_numeric(s, errors="coerce").eq(1).sum())),
        AvgRiskProbability=("risk_probability", lambda s: pd.to_numeric(s, errors="coerce").mean()),
    ).reset_index()
    grouped["Support load %"] = 100 * (grouped["FollowUp"] + grouped["Targeted"]) / grouped["Students"].clip(lower=1)
    grouped["Prediction coverage %"] = 100 * grouped["Predictions"] / grouped["Students"].clip(lower=1)
    grouped["Model flagged %"] = np.where(
        grouped["Predictions"].gt(0),
        100 * grouped["ModelFlagged"] / grouped["Predictions"],
        np.nan,
    )
    return grouped.sort_values(["Support load %", "AvgSeverity"], ascending=False)


def intervention_workload(quarter: str, modules: list[str] | None = None, presentations: list[str] | None = None) -> pd.DataFrame:
    summary = load_recommendation_summary(quarter)
    if summary.empty:
        return pd.DataFrame()
    if modules:
        summary = summary[summary["code_module"].isin(modules)]
    if presentations:
        summary = summary[summary["code_presentation"].isin(presentations)]
    counts = summary["intervention_level"].fillna("No Additional Action").value_counts().rename_axis("Intervention").reset_index(name="Students")
    counts["Share %"] = (100 * counts["Students"] / max(counts["Students"].sum(), 1)).round(1)
    return counts


def fairness_exposure(quarter: str, attribute: str, modules: list[str] | None = None, presentations: list[str] | None = None) -> pd.DataFrame:
    summary = load_recommendation_summary(quarter)
    info = load_student_info()
    if summary.empty or attribute not in info.columns:
        return pd.DataFrame()
    cols = ["id_student", "code_module", "code_presentation", attribute]
    merged = summary.merge(info[cols], on=["id_student", "code_module", "code_presentation"], how="left")
    if modules:
        merged = merged[merged["code_module"].isin(modules)]
    if presentations:
        merged = merged[merged["code_presentation"].isin(presentations)]
    merged["HighTouch"] = merged["intervention_level"].isin(["Targeted Support", "Instructor Follow-up"])
    return merged.groupby(attribute, dropna=False).agg(
        Students=("id_student", "nunique"),
        HigherTouchSupport=("HighTouch", "mean"),
        AvgRecommendations=("n_recs", "mean"),
    ).reset_index().assign(**{"Higher-touch support %": lambda d: (100 * d["HigherTouchSupport"]).round(1)})[[attribute, "Students", "Higher-touch support %", "AvgRecommendations"]]


def historical_outcomes(modules: list[str] | None = None, presentations: list[str] | None = None) -> pd.DataFrame:
    info = load_student_info().copy()
    if modules:
        info = info[info["code_module"].isin(modules)]
    if presentations:
        info = info[info["code_presentation"].isin(presentations)]
    if info.empty:
        return pd.DataFrame()
    return info.groupby("final_result").size().rename("Students").reset_index().rename(columns={"final_result": "Outcome"})
