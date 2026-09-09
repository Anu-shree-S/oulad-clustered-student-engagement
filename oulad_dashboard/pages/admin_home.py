"""TrackWise Administrator / Programme Intelligence dashboard.

Hierarchy:
1) global programme / module / presentation intelligence;
2) selected module-presentation mirrors the Instructor analytics;
3) selected learner mirrors the Student learning dashboard.

Operational support views remain checkpoint-safe. Evaluation-cohort withdrawal timing is descriptive context only and never feeds current support status.
Final outcomes remain excluded from operational support analytics.
"""

from __future__ import annotations

from html import escape
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.permissions import require_role
from components.layout import render_empty_state, render_page_heading, ribbon_start
from services.data_service import load_dashboard_data, load_student_info
from services.intervention_service import list_interventions
from services.learning_service import (
    QUARTER_LABELS,
    cohort_priority_table,
    cohort_summary,
    common_issues,
    load_quarter_comparison,
    load_recommendation_summary,
    prediction_for_student,
    student_behaviour_tiles,
    student_learning_pattern,
    student_recommendations,
    student_strengths_opportunities,
)

QUARTER_ORDER = ["Q1", "Q2", "Q3", "Q4"]
SUPPORT_ORDER = ["On Track", "Needs Attention", "Priority Support"]

SUPPORT_META = {
    "On Track": {
        "bg": "#EAF7EE",
        "border": "#A8DDB7",
        "text": "#166534",
        "chip": "#D5F0DD",
        "icon": "●",
        "rank": 2,
    },
    "Needs Attention": {
        "bg": "#FFF4DF",
        "border": "#F4CF8A",
        "text": "#9A5B00",
        "chip": "#FCE8BC",
        "icon": "●",
        "rank": 1,
    },
    "Priority Support": {
        "bg": "#FDECEC",
        "border": "#F0B0B0",
        "text": "#A42B2B",
        "chip": "#F8D4D4",
        "icon": "●",
        "rank": 0,
    },
}

BEHAVIOUR_META = {
    "Strong": ("#E7F6EC", "#A8DDB7", "#166534"),
    "Steady": ("#EEF8F1", "#B9E1C5", "#267044"),
    "Building": ("#FFF4DF", "#F4CF8A", "#9A5B00"),
    "Opportunity": ("#FDECEC", "#F0B0B0", "#A42B2B"),
    "Observed": ("#F3F5F8", "#D8DEE8", "#556070"),
}

CONTENT_TYPES = {
    "subpage", "homepage", "oucontent", "resource", "url", "page",
    "folder", "glossary", "htmlactivity", "dualpane", "repeatactivity",
}
ASSESSMENT_TYPES = {"quiz", "externalquiz", "questionnaire"}
SOCIAL_TYPES = {
    "forumng", "ouwiki", "oucollaborate", "ouelluminate",
    "dataplus", "sharedsubpage",
}


def _inject_admin_styles():
    """Admin-local styling shared by the programme, instructor-mirror and student-mirror views."""
    st.markdown(
        """
        <style>
        .tw-instructor-note {
            color:#667085; font-size:.88rem; line-height:1.55; margin:.15rem 0 .9rem 0;
        }
        .tw-support-card {
            border-radius:16px; padding:18px 20px; border:1px solid;
            min-height:118px; box-shadow:0 6px 22px rgba(31,41,55,.045);
        }
        .tw-support-card .eyebrow,
        .tw-kpi .eyebrow,
        .tw-profile-card .eyebrow {
            font-size:.72rem; font-weight:800; text-transform:uppercase;
            letter-spacing:.055em; color:#667085;
        }
        .tw-support-card .value {
            font-size:1.75rem; line-height:1.1; font-weight:800; margin:.38rem 0 .25rem 0;
        }
        .tw-support-card .sub { font-size:.84rem; line-height:1.35; color:#667085; }
        .tw-kpi {
            background:#FFFFFF; border:1px solid #E3E8EF; border-radius:16px;
            padding:16px 18px; min-height:112px; box-shadow:0 6px 22px rgba(31,41,55,.035);
        }
        .tw-kpi .value {
            color:#101828; font-size:1.72rem; line-height:1.15; font-weight:800;
            margin:.38rem 0 .2rem 0;
        }
        .tw-kpi .sub { color:#667085; font-size:.82rem; line-height:1.35; }
        .tw-section-panel {
            background:#FFFFFF; border:1px solid #E3E8EF; border-radius:16px;
            padding:17px 20px 13px 20px; margin:.35rem 0 1rem 0;
            box-shadow:0 6px 22px rgba(31,41,55,.035);
        }
        .tw-profile-banner {
            border-radius:18px; padding:20px 22px; border:1px solid;
            margin:.2rem 0 1rem 0; box-shadow:0 7px 24px rgba(31,41,55,.05);
        }
        .tw-profile-banner .student-id {
            font-size:1.35rem; font-weight:800; color:#101828; margin:.15rem 0 .25rem 0;
        }
        .tw-profile-banner .status { font-size:1.65rem; font-weight:800; }
        .tw-profile-banner .desc { color:#475467; font-size:.91rem; line-height:1.5; margin-top:.35rem; }
        .tw-profile-card {
            background:#FFFFFF; border:1px solid #E3E8EF; border-radius:14px;
            padding:14px 16px; min-height:86px;
        }
        .tw-profile-card .value { color:#101828; font-weight:750; font-size:1rem; margin-top:.28rem; }
        .tw-behaviour-card {
            border-radius:15px; border:1px solid; padding:16px 17px; min-height:132px;
            margin-bottom:.75rem; box-shadow:0 4px 16px rgba(31,41,55,.03);
        }
        .tw-behaviour-card .label {
            color:#5B6472; font-size:.72rem; font-weight:800; text-transform:uppercase;
            letter-spacing:.045em;
        }
        .tw-behaviour-card .value { color:#101828; font-size:1.18rem; font-weight:800; margin:.42rem 0 .25rem 0; }
        .tw-behaviour-card .value.relative-indicator {
            color:#667085; font-size:.80rem; font-weight:500; margin:.44rem 0 .18rem 0;
        }
        .tw-behaviour-card .status { font-size:.86rem; font-weight:800; }
        .tw-behaviour-card .status.primary-status {
            font-size:1.18rem; line-height:1.2; font-weight:800; margin:.12rem 0 .18rem 0;
        }
        .tw-behaviour-card .meaning { color:#667085; font-size:.80rem; line-height:1.35; margin-top:.38rem; }
        .tw-priority-rec {
            background:#EEF4FF; border:1px solid #CAD9F4; border-left:6px solid #6F94D0;
            border-radius:16px; padding:18px 20px; margin:.9rem 0 1.25rem 0;
            box-shadow:0 8px 24px rgba(31,41,55,.04);
        }
        .tw-priority-rec .eyebrow {
            color:#667085; font-size:.72rem; font-weight:800; text-transform:uppercase; letter-spacing:.055em;
        }
        .tw-priority-rec .gap { color:#667085; font-size:.80rem; margin:.35rem 0 .45rem 0; }
        .tw-priority-rec .recommendation { color:#101828; font-size:1.08rem; font-weight:750; line-height:1.5; }
        .tw-priority-rec .reason { color:#53657D; font-size:.84rem; line-height:1.45; margin-top:.55rem; }
        .tw-rec-card {
            background:#FFFFFF; border:1px solid #E3E8EF; border-left:5px solid #6E8FC7;
            border-radius:14px; padding:15px 17px; margin:.5rem 0 .8rem 0;
        }
        .tw-rec-card .category {
            display:inline-block; border-radius:999px; background:#EEF3FA; color:#405A7A;
            padding:3px 9px; font-size:.70rem; font-weight:800; text-transform:uppercase;
            letter-spacing:.035em;
        }
        .tw-rec-card h4 { color:#101828; margin:.48rem 0 .35rem 0; font-size:1rem; }
        .tw-rec-card p { color:#667085; font-size:.86rem; line-height:1.45; margin:.2rem 0; }
        .tw-rec-card .action { color:#344054; font-weight:650; margin-top:.55rem; }
        .tw-legend {
            display:flex; gap:10px; flex-wrap:wrap; margin:.4rem 0 .9rem 0;
        }
        .tw-legend span {
            border-radius:999px; padding:4px 9px; font-size:.75rem; font-weight:750;
            border:1px solid #E3E8EF; background:#fff;
        }
        div[data-baseweb="tab-list"] { gap:.45rem; }
        button[data-baseweb="tab"] {
            border-radius:10px 10px 0 0; padding-left:1rem; padding-right:1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _base_figure_layout(fig: go.Figure, *, x_title: str = "", y_title: str = "", height: int = 330):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#667085"),
        xaxis=dict(title=x_title, gridcolor="#E8EDF3", zeroline=False),
        yaxis=dict(title=y_title, gridcolor="#E8EDF3", zeroline=False),
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", font_color="#344054"),
    )


def _metric_card(label: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class='tw-kpi'>
          <div class='eyebrow'>{escape(str(label))}</div>
          <div class='value'>{escape(str(value))}</div>
          <div class='sub'>{escape(str(subtitle))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _support_card(label: str, value: str, subtitle: str, support_level: str):
    meta = SUPPORT_META[support_level]
    st.markdown(
        f"""
        <div class='tw-support-card' style='background:{meta['bg']};border-color:{meta['border']}'>
          <div class='eyebrow'>{escape(str(label))}</div>
          <div class='value' style='color:{meta['text']}'>{escape(str(value))}</div>
          <div class='sub'>{escape(str(subtitle))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _support_banner(student_id: int, level: str, pattern_label: str, opportunity: str):
    meta = SUPPORT_META[level]
    if level == "On Track":
        message = "Current learning behaviour is broadly steady. Continue normal monitoring and reinforce the habits that are working."
    elif level == "Needs Attention":
        message = "One or more modifiable learning behaviours would benefit from timely instructor attention at this checkpoint."
    else:
        message = "Several behavioural signals indicate that structured instructor follow-up should be prioritised at this checkpoint."

    st.markdown(
        f"""
        <div class='tw-profile-banner' style='background:{meta['bg']};border-color:{meta['border']}'>
          <div class='eyebrow'>Student support profile</div>
          <div class='student-id'>Student ID {escape(str(student_id))}</div>
          <div class='status' style='color:{meta['text']}'>{escape(level)}</div>
          <div class='desc'>{escape(message)}<br>
          <b>Learning pattern:</b> {escape(str(pattern_label))} &nbsp;·&nbsp;
          <b>Main opportunity:</b> {escape(str(opportunity or 'No priority opportunity surfaced'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _safe_number(value, default=None):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return default
    return float(parsed)


def _first_existing(row, names, default=""):
    for name in names:
        if isinstance(row, dict) and name in row and pd.notna(row.get(name)):
            value = row.get(name)
            if str(value).strip():
                return value
        if isinstance(row, pd.Series) and name in row.index and pd.notna(row.get(name)):
            value = row.get(name)
            if str(value).strip():
                return value
    return default


def _normalise_support(row) -> str:
    """Map recommendation-layer wording onto the three shared support levels."""
    key = str(_first_existing(row, ["support_status_key"], "")).strip().lower()
    if key == "steady":
        return "On Track"
    if key == "attention":
        return "Needs Attention"
    if key == "support":
        return "Priority Support"

    pieces = [
        _first_existing(row, ["instructor_support_status", "support_status", "Support priority"]),
        _first_existing(row, ["intervention_level", "Recommended support"]),
    ]
    text = " ".join(str(x) for x in pieces if x).lower()

    if any(token in text for token in ["priority", "urgent", "instructor follow-up", "high-touch", "support recommended"]):
        return "Priority Support"
    if any(token in text for token in ["attention", "targeted support", "watch", "self-guided", "building"]):
        return "Needs Attention"
    if any(token in text for token in ["on track", "no additional action", "steady", "going well"]):
        return "On Track"
    return "Needs Attention"


def _load_raw_tables() -> dict:
    """Normalise the dashboard data service into the OULAD tables used here."""
    try:
        loaded = load_dashboard_data()
    except Exception:
        loaded = None

    result = {
        "student_info": pd.DataFrame(),
        "student_vle": pd.DataFrame(),
        "student_assessment": pd.DataFrame(),
        "assessments": pd.DataFrame(),
        "courses": pd.DataFrame(),
        "vle_meta": pd.DataFrame(),
    }

    if isinstance(loaded, dict):
        aliases = {
            "student_info": ("studentInfo", "student_info"),
            "student_vle": ("studentVle", "student_vle"),
            "student_assessment": ("studentAssessment", "student_assessment"),
            "assessments": ("assessments",),
            "courses": ("courses",),
            "vle_meta": ("vle", "VLE", "vle_metadata"),
        }
        for target, names in aliases.items():
            for name in names:
                value = loaded.get(name)
                if isinstance(value, pd.DataFrame):
                    result[target] = value.copy()
                    break
    elif isinstance(loaded, (list, tuple)):
        # Common loader order: studentInfo, studentVle, studentAssessment,
        # assessments, studentRegistration, courses, vle.
        if len(loaded) > 0 and isinstance(loaded[0], pd.DataFrame):
            result["student_info"] = loaded[0].copy()
        if len(loaded) > 1 and isinstance(loaded[1], pd.DataFrame):
            result["student_vle"] = loaded[1].copy()
        if len(loaded) > 2 and isinstance(loaded[2], pd.DataFrame):
            result["student_assessment"] = loaded[2].copy()
        if len(loaded) > 3 and isinstance(loaded[3], pd.DataFrame):
            result["assessments"] = loaded[3].copy()
        if len(loaded) > 5 and isinstance(loaded[5], pd.DataFrame):
            result["courses"] = loaded[5].copy()
        if len(loaded) > 6 and isinstance(loaded[6], pd.DataFrame):
            result["vle_meta"] = loaded[6].copy()

        # Schema-based fallback in case the data-service tuple order changes.
        for value in loaded[4:]:
            if not isinstance(value, pd.DataFrame) or value.empty:
                continue
            cols = set(value.columns)
            if {"id_site", "activity_type"}.issubset(cols):
                result["vle_meta"] = value.copy()
            if {"code_module", "code_presentation"}.issubset(cols) and (
                "module_presentation_length" in cols or "length" in cols
            ):
                result["courses"] = value.copy()

    # load_student_info is a reliable fallback for cohort membership.
    if result["student_info"].empty:
        try:
            info = load_student_info()
            if isinstance(info, pd.DataFrame):
                result["student_info"] = info.copy()
        except Exception:
            pass

    return result


def _course_weeks(raw: dict, module: str, presentation: str) -> int:
    courses = raw.get("courses", pd.DataFrame())
    if isinstance(courses, pd.DataFrame) and not courses.empty and {"code_module", "code_presentation"}.issubset(courses.columns):
        course = courses[
            courses["code_module"].astype(str).eq(str(module))
            & courses["code_presentation"].astype(str).eq(str(presentation))
        ]
        if not course.empty:
            for col in ("module_presentation_length", "length", "course_weeks"):
                if col in course.columns:
                    val = _safe_number(course.iloc[0].get(col))
                    if val is not None:
                        # OULAD module_presentation_length is in days.
                        if val > 60:
                            return max(1, int(math.ceil(val / 7.0)))
                        return max(1, int(round(val)))

    vle = raw.get("student_vle", pd.DataFrame())
    if isinstance(vle, pd.DataFrame) and not vle.empty and {"code_module", "code_presentation", "date"}.issubset(vle.columns):
        course = vle[
            vle["code_module"].astype(str).eq(str(module))
            & vle["code_presentation"].astype(str).eq(str(presentation))
        ].copy()
        dates = pd.to_numeric(course.get("date"), errors="coerce")
        dates = dates[dates.ge(0)]
        if not dates.empty:
            return max(1, int(math.ceil((float(dates.max()) + 1) / 7.0)))

    return 38


def _quarter_bounds(course_weeks: int, quarter: str) -> tuple[int, int]:
    if course_weeks == 38:
        ends = [10, 19, 29, 38]
    elif course_weeks == 34:
        ends = [9, 17, 26, 34]
    else:
        ends = [
            max(1, int(math.ceil(course_weeks * .25))),
            max(1, int(math.ceil(course_weeks * .50))),
            max(1, int(math.ceil(course_weeks * .75))),
            course_weeks,
        ]
    idx = ["Q1", "Q2", "Q3", "Q4"].index(quarter)
    start = 1 if idx == 0 else ends[idx - 1] + 1
    return start, ends[idx]


def _cohort_info(raw: dict, module: str, presentation: str) -> pd.DataFrame:
    info = raw.get("student_info", pd.DataFrame())
    if not isinstance(info, pd.DataFrame) or info.empty:
        return pd.DataFrame()
    needed = {"id_student", "code_module", "code_presentation"}
    if not needed.issubset(info.columns):
        return pd.DataFrame()
    return info[
        info["code_module"].astype(str).eq(str(module))
        & info["code_presentation"].astype(str).eq(str(presentation))
    ].copy()


def _prepare_vle(raw: dict, module: str, presentation: str) -> pd.DataFrame:
    vle = raw.get("student_vle", pd.DataFrame())
    if not isinstance(vle, pd.DataFrame) or vle.empty:
        return pd.DataFrame()
    needed = {"id_student", "code_module", "code_presentation", "date", "sum_click"}
    if not needed.issubset(vle.columns):
        return pd.DataFrame()
    course = vle[
        vle["code_module"].astype(str).eq(str(module))
        & vle["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if course.empty:
        return course
    course["id_student"] = pd.to_numeric(course["id_student"], errors="coerce")
    course["date"] = pd.to_numeric(course["date"], errors="coerce")
    course["sum_click"] = pd.to_numeric(course["sum_click"], errors="coerce").fillna(0).clip(lower=0)
    course = course[course["date"].ge(0)].copy()
    course["week"] = (course["date"] // 7 + 1).astype(int)

    # Hosted deployment already carries a compact activity_type category in
    # dashboard_weekly_vle.parquet, so no raw vle.csv lookup is required.
    if "activity_type" in course.columns and course["activity_type"].notna().any():
        course["dimension"] = course["activity_type"].map(_engagement_dimension)
    else:
        meta = raw.get("vle_meta", pd.DataFrame())
        if (
            isinstance(meta, pd.DataFrame)
            and not meta.empty
            and {"id_site", "activity_type"}.issubset(meta.columns)
            and "id_site" in course.columns
        ):
            lookup = meta[["id_site", "activity_type"]].drop_duplicates("id_site")
            course = course.merge(lookup, on="id_site", how="left")
            course["dimension"] = course["activity_type"].map(_engagement_dimension)
        else:
            course["dimension"] = "other"
    return course


def _engagement_dimension(value) -> str:
    text = str(value).strip().lower()
    if text in CONTENT_TYPES:
        return "content"
    if text in ASSESSMENT_TYPES:
        return "assessment"
    if text in SOCIAL_TYPES:
        return "social"
    return "other"


def _class_weekly_metrics(raw: dict, module: str, presentation: str, start_week: int, end_week: int) -> tuple[pd.DataFrame, dict]:
    """Class weekly engagement averages and active-student percentage for the selected quarter."""
    cohort = _cohort_info(raw, module, presentation)
    course = _prepare_vle(raw, module, presentation)
    if cohort.empty or course.empty:
        return pd.DataFrame(), {}

    ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique())
    class_size = max(len(ids), 1)
    weeks = pd.Index(range(start_week, end_week + 1), name="week")
    current = course[course["week"].between(start_week, end_week)].copy()

    out = pd.DataFrame({"week": weeks})
    dim_map = {
        "Course Materials": "content",
        "Practice & Assessments": "assessment",
        "Learning With Others": "social",
    }
    dimensions_available = current["dimension"].ne("other").any() if "dimension" in current.columns else False
    if dimensions_available:
        for label, dim in dim_map.items():
            weekly_total = current[current["dimension"].eq(dim)].groupby("week")["sum_click"].sum()
            out[label] = weekly_total.reindex(weeks, fill_value=0.0).to_numpy(dtype=float) / class_size

    overall = current.groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0)
    out["Overall Engagement"] = overall.to_numpy(dtype=float) / class_size

    active = (
        current.groupby(["week", "id_student"])["sum_click"].sum().gt(0)
        .groupby("week").sum().reindex(weeks, fill_value=0)
    )
    out["Students Active (%)"] = active.to_numpy(dtype=float) / class_size * 100.0

    student_active_weeks = (
        current.groupby(["id_student", "week"])["sum_click"].sum().gt(0)
        .groupby("id_student").sum().reindex(ids, fill_value=0)
    )
    available_weeks = max(end_week - start_week + 1, 1)
    mean_active_ratio = float((student_active_weeks / available_weeks).mean() * 100) if len(ids) else 0.0

    stats = {
        "class_size": class_size,
        "mean_active_ratio": mean_active_ratio,
        "dimensions_available": dimensions_available,
        "quarter_total_engagement_avg": float(current["sum_click"].sum()) / class_size,
    }
    return out, stats


def _assessment_labels(due: pd.DataFrame) -> pd.DataFrame:
    due = due.sort_values(["date", "id_assessment"]).copy()
    counts = {}
    labels = []
    for _, row in due.iterrows():
        kind = str(row.get("assessment_type", "Task")).upper()
        counts[kind] = counts.get(kind, 0) + 1
        labels.append(f"{kind} {counts[kind]}")
    due["Assessment"] = labels
    return due


def _assessment_checkpoint(raw: dict, module: str, presentation: str, end_week: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Assessment metrics using only submissions known by the selected checkpoint."""
    assessments = raw.get("assessments", pd.DataFrame())
    sa = raw.get("student_assessment", pd.DataFrame())
    cohort = _cohort_info(raw, module, presentation)
    if not isinstance(assessments, pd.DataFrame) or assessments.empty or cohort.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    ass = assessments[
        assessments["code_module"].astype(str).eq(str(module))
        & assessments["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if ass.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    ass["date"] = pd.to_numeric(ass.get("date"), errors="coerce")
    end_day = int(end_week) * 7
    due = ass[ass["date"].notna() & ass["date"].le(end_day)].copy()
    if due.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "due_count": 0, "submission_rate": 0.0, "not_submitted": 0,
            "avg_score": None, "class_size": cohort["id_student"].nunique(),
        }
    due = _assessment_labels(due)

    class_size = int(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().nunique())
    class_size = max(class_size, 1)

    if not isinstance(sa, pd.DataFrame) or sa.empty:
        if "weight" not in due.columns:
            due["weight"] = pd.NA
        metrics = due[["id_assessment", "Assessment", "assessment_type", "date", "weight"]].copy()
        metrics["Submitted"] = 0
        metrics["Submission rate (%)"] = 0.0
        metrics["Not submitted"] = class_size
        metrics["Late"] = 0
        metrics["Average score (%)"] = pd.NA
        return metrics, pd.DataFrame(), {
            "due_count": len(due), "submission_rate": 0.0,
            "not_submitted": class_size * len(due), "avg_score": None,
            "class_size": class_size,
        }

    known = sa.copy()
    known["id_student"] = pd.to_numeric(known.get("id_student"), errors="coerce")
    known["date_submitted"] = pd.to_numeric(known.get("date_submitted"), errors="coerce")
    known["score"] = pd.to_numeric(known.get("score"), errors="coerce")
    known = known[
        known["id_assessment"].isin(due["id_assessment"])
        & known["date_submitted"].notna()
        & known["date_submitted"].le(end_day)
    ].copy()
    known = known.merge(due[["id_assessment", "Assessment", "date"]], on="id_assessment", how="inner", suffixes=("", "_due"))

    rows = []
    for _, assessment in due.iterrows():
        aid = assessment["id_assessment"]
        sub = known[known["id_assessment"].eq(aid)].copy()
        submitted = int(sub["id_student"].nunique())
        late = int((sub["date_submitted"] > float(assessment["date"])).sum()) if not sub.empty else 0
        avg_score = sub["score"].mean() if not sub.empty else pd.NA
        rows.append({
            "id_assessment": aid,
            "Assessment": assessment["Assessment"],
            "assessment_type": assessment.get("assessment_type", ""),
            "date": assessment["date"],
            "weight": assessment.get("weight", pd.NA),
            "Submitted": submitted,
            "Submission rate (%)": submitted / class_size * 100.0,
            "Not submitted": max(class_size - submitted, 0),
            "Late": late,
            "Average score (%)": avg_score,
        })
    metrics = pd.DataFrame(rows)

    total_opportunities = class_size * len(due)
    submitted_total = int(metrics["Submitted"].sum())
    stats = {
        "due_count": int(len(due)),
        "submission_rate": submitted_total / max(total_opportunities, 1) * 100.0,
        "not_submitted": int(max(total_opportunities - submitted_total, 0)),
        "avg_score": float(known["score"].mean()) if not known.empty and known["score"].notna().any() else None,
        "class_size": class_size,
    }
    score_distribution = known[["id_assessment", "Assessment", "id_student", "score", "date_submitted", "date"]].copy()
    return metrics, score_distribution, stats


def _student_quarter_metrics(raw: dict, module: str, presentation: str, start_week: int, end_week: int, assessment_metrics: pd.DataFrame) -> pd.DataFrame:
    """One checkpoint-safe metric row per learner for Support Queue enrichment."""
    cohort = _cohort_info(raw, module, presentation)
    if cohort.empty:
        return pd.DataFrame()
    ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique(), name="id_student")
    result = pd.DataFrame({"id_student": ids})
    available_weeks = max(end_week - start_week + 1, 1)

    course = _prepare_vle(raw, module, presentation)
    if not course.empty:
        current = course[course["week"].between(start_week, end_week)].copy()
        totals = current.groupby("id_student")["sum_click"].sum().reindex(ids, fill_value=0.0)
        active = (
            current.groupby(["id_student", "week"])["sum_click"].sum().gt(0)
            .groupby("id_student").sum().reindex(ids, fill_value=0)
        )
        result["Active Weeks %"] = (active.to_numpy(dtype=float) / available_weeks * 100.0)
        result["Quarter Engagement"] = totals.to_numpy(dtype=float)
        class_avg = float(totals.mean()) if len(totals) else 0.0
        result["Engagement vs Class %"] = result["Quarter Engagement"].apply(
            lambda x: (float(x) / class_avg * 100.0) if class_avg > 0 else 0.0
        )
    else:
        result["Active Weeks %"] = pd.NA
        result["Quarter Engagement"] = pd.NA
        result["Engagement vs Class %"] = pd.NA

    due_ids = assessment_metrics["id_assessment"].tolist() if not assessment_metrics.empty else []
    due_count = len(due_ids)
    sa = raw.get("student_assessment", pd.DataFrame())
    if due_count and isinstance(sa, pd.DataFrame) and not sa.empty:
        end_day = int(end_week) * 7
        tmp = sa[sa["id_assessment"].isin(due_ids)].copy()
        tmp["id_student"] = pd.to_numeric(tmp.get("id_student"), errors="coerce")
        tmp["date_submitted"] = pd.to_numeric(tmp.get("date_submitted"), errors="coerce")
        tmp["score"] = pd.to_numeric(tmp.get("score"), errors="coerce")
        tmp = tmp[tmp["date_submitted"].notna() & tmp["date_submitted"].le(end_day)]
        due_dates = assessment_metrics[["id_assessment", "date"]].copy()
        tmp = tmp.merge(due_dates, on="id_assessment", how="inner")
        tmp["_late_flag"] = (tmp["date_submitted"] > tmp["date"]).astype(int)
        grouped = tmp.groupby("id_student")
        submitted = grouped["id_assessment"].nunique().reindex(ids, fill_value=0)
        late = grouped["_late_flag"].sum().reindex(ids, fill_value=0) if not tmp.empty else pd.Series(0, index=ids)
        avg_score = grouped["score"].mean().reindex(ids)
        result["Assessments Submitted"] = submitted.to_numpy(dtype=int)
        result["Assessments Due"] = due_count
        result["Late Submissions"] = late.to_numpy(dtype=int)
        result["Average Score %"] = avg_score.to_numpy()
    else:
        result["Assessments Submitted"] = 0
        result["Assessments Due"] = due_count
        result["Late Submissions"] = 0
        result["Average Score %"] = pd.NA

    return result


def _enrich_queue(queue: pd.DataFrame, raw_metrics: pd.DataFrame) -> pd.DataFrame:
    if queue is None or queue.empty:
        return pd.DataFrame()
    out = queue.copy()
    if "id_student" not in out.columns:
        return out
    out["id_student"] = pd.to_numeric(out["id_student"], errors="coerce")
    out = out.dropna(subset=["id_student"]).copy()
    out["id_student"] = out["id_student"].astype(int)
    if isinstance(raw_metrics, pd.DataFrame) and not raw_metrics.empty:
        out = out.merge(raw_metrics, on="id_student", how="left")
    out["Support Status"] = out.apply(lambda row: _normalise_support(row), axis=1)
    out["Support Rank"] = out["Support Status"].map({k: v["rank"] for k, v in SUPPORT_META.items()}).fillna(1)
    return out


def _queue_table(enriched: pd.DataFrame, *, compact: bool = False):
    if enriched.empty:
        render_empty_state(
            "Support queue unavailable",
            "Connect the recommendation summary/details exports to populate the instructor support queue.",
        )
        return

    display = pd.DataFrame()
    display["Student ID"] = enriched["id_student"].astype(int)
    display["Support Status"] = enriched["Support Status"]
    display["Main Behavioural Opportunity"] = enriched.apply(
        lambda r: _first_existing(r, ["Main opportunity", "main_opportunity", "primary_opportunity", "top_opportunity"], "—"), axis=1
    )
    if "Active Weeks %" in enriched.columns:
        display["Active Weeks"] = pd.to_numeric(enriched["Active Weeks %"], errors="coerce").map(lambda x: f"{x:.0f}%" if pd.notna(x) else "—")
    if "Engagement vs Class %" in enriched.columns:
        display["Engagement vs Class"] = pd.to_numeric(enriched["Engagement vs Class %"], errors="coerce").map(lambda x: f"{x:.0f}%" if pd.notna(x) else "—")
    if {"Assessments Submitted", "Assessments Due"}.issubset(enriched.columns):
        display["Assessments"] = enriched.apply(
            lambda r: f"{int(r.get('Assessments Submitted', 0) or 0)} / {int(r.get('Assessments Due', 0) or 0)}", axis=1
        )
    if "Late Submissions" in enriched.columns:
        display["Late"] = pd.to_numeric(enriched["Late Submissions"], errors="coerce").fillna(0).astype(int)
    display["Suggested Support"] = enriched.apply(
        lambda r: _first_existing(r, ["intervention_level", "Recommended support", "suggested_support"], "Review learner profile"), axis=1
    )

    if compact:
        display = display.head(8)

    def _row_style(row):
        level = row.get("Support Status", "Needs Attention")
        return [f"background-color: {SUPPORT_META.get(level, SUPPORT_META['Needs Attention'])['bg']}" for _ in row]

    styled = display.style.apply(_row_style, axis=1)
    st.dataframe(styled, hide_index=True, use_container_width=True, height=min(470, 38 + len(display) * 35))


def _tile_display_value(tile: dict) -> str:
    """Return an intuitive display value for behavioural indicator cards.

    Engagement features are course-normalised relative indicators. Their raw
    values can be small fractions, so formatting them as percentages can produce
    misleading values such as ``0%`` even when the peer-relative status is
    ``Steady``. Match the refined Student page by keeping those indicators
    qualitative, while true ratio/count measures keep their natural units.
    """
    key = str(tile.get("key") or "")
    value = pd.to_numeric(pd.Series([tile.get("value")]), errors="coerce").iloc[0]
    value = None if pd.isna(value) else float(value)

    if key in {"study_consistency", "study_spacing", "learning_balance"} and value is not None:
        # These features are genuine 0-1 ratios.
        return f"{100 * value:.0f}%"

    if key == "deadline_adherence" and value is not None:
        return f"{int(round(value))} late"

    if key == "study_timing":
        return "Timing pattern"

    if key in {
        "overall_engagement",
        "course_materials",
        "assessment_engagement",
        "social_engagement",
    }:
        return "Relative indicator"

    return str(tile.get("value_text") or "Observed")


def _behaviour_cards(tiles):
    if not tiles:
        render_empty_state(
            "Behavioural profile unavailable",
            "The checkpoint behavioural export is needed to show the learner's pedagogical indicators.",
        )
        return
    for start in range(0, len(tiles), 3):
        cols = st.columns(3)
        for col, tile in zip(cols, tiles[start:start + 3]):
            status = str(tile.get("status") or "Observed")
            bg, border, text = BEHAVIOUR_META.get(status, BEHAVIOUR_META["Observed"])
            meaning = {
                "Strong": "A comparatively strong learning habit at this checkpoint.",
                "Steady": "Broadly steady within this course context.",
                "Building": "A developing habit that may benefit from reinforcement.",
                "Opportunity": "A clear behavioural opportunity for targeted support.",
                "Observed": "Observed behaviour without a reliable relative status.",
            }.get(status, "Observed learning behaviour.")
            with col:
                display_value = _tile_display_value(tile)
                value_class = "value relative-indicator" if display_value == "Relative indicator" else "value"
                status_class = "status primary-status" if display_value == "Relative indicator" else "status"
                st.markdown(
                    f"""
                    <div class='tw-behaviour-card' style='background:{bg};border-color:{border}'>
                      <div class='label'>{escape(str(tile.get('label', 'Learning habit')))}</div>
                      <div class='{value_class}'>{escape(display_value)}</div>
                      <div class='{status_class}' style='color:{text}'>{escape(status)}</div>
                      <div class='meaning'>{escape(meaning)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


PRIORITY_RECOMMENDATION_COPY = {
    "assessment timing opportunity": (
        "Recommend that the learner starts the next assessment several days earlier than usual and uses the additional time to review instructions, ask questions and revise before submission."
    ),
    "deadline planning opportunity": (
        "Recommend that the learner plans upcoming assessment deadlines in advance by setting an earlier personal reminder and breaking the work into smaller steps, reducing last-minute pressure."
    ),
    "assessment practice opportunity": (
        "Recommend that the learner completes at least one available quiz or self-check activity this week and uses the result to identify topics that need further review."
    ),
    "course material engagement opportunity": (
        "Recommend that the learner reconnects with the core course materials before the next study or assessment session by reviewing the key resource for the upcoming topic and using it to guide practice."
    ),
    "study spacing opportunity": (
        "Recommend that the learner spreads study across two or three shorter sessions on different days this week instead of concentrating activity into one long burst, reinforcing learning more regularly."
    ),
    "study consistency opportunity": (
        "Recommend that the learner builds a steadier weekly routine by scheduling three small study windows this week—even 15–30 minutes each—so they stay connected to the course and prevent work from accumulating."
    ),
    "peer learning opportunity": (
        "Recommend that the learner participates in collaborative learning by reading the current discussion and contributing one question, reply or useful comment this week to test and clarify understanding."
    ),
}


def _priority_recommendation_payload(recs, fallback_issue="") -> tuple[str, str, str]:
    rec = recs[0] if recs else {}
    rec = rec if isinstance(rec, dict) else {}

    def first(keys, default=""):
        for key in keys:
            value = rec.get(key)
            if value is not None and str(value).strip() and str(value).strip().lower() != "nan":
                return str(value).strip()
        return default

    issue = first(["issue_label", "issue", "main_opportunity", "primary_opportunity"], str(fallback_issue or "").strip())
    mapped = PRIORITY_RECOMMENDATION_COPY.get(issue.lower()) if issue else None
    action = first(["action", "suggested_action", "next_step"])
    title = first(["title", "recommendation_title"])
    why = first(["why", "explanation", "detail", "what_we_noticed"])

    if mapped:
        recommendation = mapped
    elif action and action.lower() not in {"review learner profile", "review this learner"}:
        recommendation = action.rstrip(".") + "."
    elif title and (not issue or title.lower() != issue.lower()) and "opportunity" not in title.lower():
        recommendation = title.rstrip(".") + "."
    elif issue:
        focus = issue.lower().replace(" opportunity", "").strip()
        recommendation = (
            f"Recommend targeted support to strengthen {focus} by agreeing one small, specific action for the learner to repeat consistently before the next checkpoint."
        )
    else:
        recommendation = (
            "No corrective behavioural gap currently crosses the recommendation threshold. Continue normal monitoring and reinforce the learning habits that are working."
        )

    return issue if issue else "No priority behavioural gap", recommendation, why


def _render_priority_recommendation_block(recs, fallback_issue=""):
    gap, recommendation, why = _priority_recommendation_payload(recs, fallback_issue)
    reason_html = (
        f"<div class='reason'><b>Why this is prioritised:</b> {escape(why)}</div>"
        if why else ""
    )
    st.markdown(
        f"""
        <div class='tw-priority-rec'>
          <div class='eyebrow'>Priority recommendation for this learner</div>
          <div class='gap'>Prioritised behavioural gap: {escape(gap)}</div>
          <div class='recommendation'>{escape(recommendation)}</div>
          {reason_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _recommendation_cards(recs, support_level="Needs Attention"):
    if not recs:
        st.success("No corrective recommendation crosses the behavioural threshold at this checkpoint.")
        return
    border = SUPPORT_META.get(support_level, SUPPORT_META["Needs Attention"])["border"]
    for rec in recs:
        st.markdown(
            f"""
            <div class='tw-rec-card' style='border-left-color:{border}'>
              <span class='category'>{escape(str(rec.get('category', 'Recommendation')))}</span>
              <h4>{escape(str(rec.get('title', 'Recommended support')))}</h4>
              <p><b>What we noticed:</b> {escape(str(rec.get('why', 'A behavioural opportunity was identified.')))}</p>
              <p class='action'><b>Suggested instructor response:</b> {escape(str(rec.get('action', 'Review this learner and choose an appropriate support response.')))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _student_row(info: pd.DataFrame, student_id: int, module: str, presentation: str) -> dict:
    if not isinstance(info, pd.DataFrame) or info.empty:
        return {}
    rows = info[
        pd.to_numeric(info["id_student"], errors="coerce").eq(int(student_id))
        & info["code_module"].astype(str).eq(str(module))
        & info["code_presentation"].astype(str).eq(str(presentation))
    ]
    return {} if rows.empty else rows.iloc[0].to_dict()


def _assessment_boxplot(score_distribution: pd.DataFrame, student_id: int | None = None, key: str = "assessment_boxplot"):
    if score_distribution.empty:
        render_empty_state("Assessment distribution unavailable", "No submitted assessment scores are available by this checkpoint.")
        return

    fig = go.Figure()
    fig.add_trace(go.Box(
        x=score_distribution["Assessment"],
        y=score_distribution["score"],
        name="Class score distribution",
        marker_color="#83B7E7",
        line_color="#5B8FC4",
        fillcolor="rgba(131,183,231,.28)",
        boxpoints="outliers",
        hovertemplate="%{x}<br>Score: %{y:.1f}%<extra>Class distribution</extra>",
    ))

    if student_id is not None:
        mine = score_distribution[pd.to_numeric(score_distribution["id_student"], errors="coerce").eq(int(student_id))].copy()
        if not mine.empty:
            fig.add_trace(go.Scatter(
                x=mine["Assessment"], y=mine["score"], mode="markers", name="Student",
                marker=dict(size=13, symbol="diamond", color="#B23A48", line=dict(color="white", width=1.5)),
                hovertemplate="%{x}<br>Student score: %{y:.1f}%<extra></extra>",
            ))

    _base_figure_layout(fig, x_title="Assessment", y_title="Score (%)", height=380)
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True, key=key)


def _detail_context_card(label: str, value: str):
    st.markdown(
        f"""
        <div class='tw-profile-card'>
          <div class='eyebrow'>{escape(str(label))}</div>
          <div class='value'>{escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _tile_group(tile: dict) -> str:
    key = str(tile.get("key") or "").lower()
    label = str(tile.get("label") or "").lower()
    if any(token in key for token in ["engagement", "content", "social"]) or any(
        token in label for token in ["engagement", "course materials", "learning with others"]
    ):
        return "Engagement"
    if any(token in key for token in ["consistency", "active_weeks", "spacing", "regularity", "entropy"]) or any(
        token in label for token in ["consistency", "active weeks", "spacing", "regularity"]
    ):
        return "Consistency"
    return "Assessment Behaviour"


def _grouped_behaviour_cards(tiles):
    if not tiles:
        render_empty_state(
            "Behavioural profile unavailable",
            "The checkpoint behavioural export is needed to show the learner's pedagogical indicators.",
        )
        return
    groups = {"Engagement": [], "Consistency": [], "Assessment Behaviour": []}
    for tile in tiles:
        groups[_tile_group(tile)].append(tile)
    for heading, group in groups.items():
        if not group:
            continue
        st.markdown(f"#### {heading}")
        _behaviour_cards(group)


def _student_engagement_detail_data(
    raw: dict,
    student_id: int,
    module: str,
    presentation: str,
    quarter: str,
    course_weeks: int,
):
    """Student current-quarter engagement with actual class averages.

    Left-chart data are the learner's weekly Content / Assessment / Social /
    Overall interactions. Q2-Q4 also return the learner's immediately previous
    quarter average weekly Overall Engagement as a single reference line.

    Right-chart data use actual current-quarter interaction totals. Class
    Average = total interactions across all enrolled students / total enrolled
    students in the module-presentation, including zero-activity learners.
    """
    cohort = _cohort_info(raw, module, presentation)
    course = _prepare_vle(raw, module, presentation)
    start_week, end_week = _quarter_bounds(course_weeks, quarter)
    if cohort.empty or course.empty:
        return pd.DataFrame(), pd.DataFrame(), None, start_week, end_week

    ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique())
    class_size = max(len(ids), 1)
    weeks = pd.Index(range(start_week, end_week + 1), name="week")
    current = course[course["week"].between(start_week, end_week)].copy()
    mine = current[current["id_student"].eq(int(student_id))].copy()

    dim_map = {
        "Course Materials": "content",
        "Practice & Assessments": "assessment",
        "Learning With Others": "social",
    }
    weekly = pd.DataFrame({"week": weeks})
    dimensions_available = current["dimension"].isin(["content", "assessment", "social"]).any()
    if dimensions_available:
        for label, dim in dim_map.items():
            vals = mine[mine["dimension"].eq(dim)].groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0)
            weekly[label] = vals.to_numpy(dtype=float)
    overall = mine.groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0)
    weekly["Overall Engagement"] = overall.to_numpy(dtype=float)

    rows = []
    if dimensions_available:
        for label, dim in dim_map.items():
            me_total = float(mine.loc[mine["dimension"].eq(dim), "sum_click"].sum())
            class_total = float(current.loc[current["dimension"].eq(dim), "sum_click"].sum())
            rows.append({"Metric": label, "Student": me_total, "Class Average": class_total / class_size})
    rows.append({
        "Metric": "Overall Engagement",
        "Student": float(mine["sum_click"].sum()),
        "Class Average": float(current["sum_click"].sum()) / class_size,
    })
    comparison = pd.DataFrame(rows)

    previous_avg = None
    q_order = ["Q1", "Q2", "Q3", "Q4"]
    q_idx = q_order.index(quarter)
    if q_idx > 0:
        prev_q = q_order[q_idx - 1]
        prev_start, prev_end = _quarter_bounds(course_weeks, prev_q)
        prev = course[
            course["id_student"].eq(int(student_id))
            & course["week"].between(prev_start, prev_end)
        ]
        previous_avg = float(prev["sum_click"].sum()) / max(prev_end - prev_start + 1, 1)

    return weekly, comparison, previous_avg, start_week, end_week


def _render_student_engagement_detail(
    raw: dict,
    student_id: int,
    module: str,
    presentation: str,
    quarter: str,
    course_weeks: int,
):
    weekly, comparison, previous_avg, start_week, end_week = _student_engagement_detail_data(
        raw, student_id, module, presentation, quarter, course_weeks
    )
    left, right = st.columns(2)
    with left:
        st.markdown("#### My Weekly Engagement – Current Quarter")
        note = (
            " The dashed line is this learner's previous-quarter average weekly Overall Engagement."
            if previous_avg is not None else ""
        )
        st.caption(f"Actual VLE interactions during {quarter}, Weeks {start_week}–{end_week}." + note)
        if weekly.empty:
            render_empty_state("Engagement unavailable", "No VLE activity data are available for this learner.")
        else:
            fig = go.Figure()
            trace_meta = [
                ("Course Materials", "#5B8FC4"),
                ("Practice & Assessments", "#D59A43"),
                ("Learning With Others", "#69AD79"),
                ("Overall Engagement", "#263A57"),
            ]
            for col, colour in trace_meta:
                if col in weekly.columns:
                    fig.add_trace(go.Scatter(
                        x=weekly["week"], y=weekly[col], mode="lines+markers", name=col,
                        line=dict(color=colour, width=3 if col == "Overall Engagement" else 2),
                        hovertemplate=f"Week %{{x}}<br>{col}: %{{y:,.0f}} interactions<extra></extra>",
                    ))
            if previous_avg is not None:
                fig.add_hline(
                    y=previous_avg, line_dash="dash", line_color="#98A2B3",
                    annotation_text="Previous Quarter Avg – Overall",
                    annotation_position="top right",
                )
            _base_figure_layout(fig, x_title="Course week", y_title="VLE interactions", height=340)
            fig.update_xaxes(dtick=1)
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, key=f"detail_engagement_weekly_{student_id}_{quarter}")

    with right:
        st.markdown("#### ME vs Class Average")
        st.caption(
            "Actual interaction totals in the selected quarter. Class Average is the arithmetic mean across all enrolled learners in this module-presentation."
        )
        if comparison.empty:
            render_empty_state("Class comparison unavailable", "Engagement comparison could not be calculated.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=comparison["Metric"], y=comparison["Student"], name="ME",
                marker_color="#4A78B6", text=comparison["Student"].map(lambda v: f"{v:,.0f}"), textposition="auto",
            ))
            fig.add_trace(go.Bar(
                x=comparison["Metric"], y=comparison["Class Average"], name="Class Average",
                marker_color="#A8C8E8", text=comparison["Class Average"].map(lambda v: f"{v:,.1f}"), textposition="auto",
            ))
            _base_figure_layout(fig, y_title="VLE interactions", height=340)
            fig.update_layout(barmode="group", hovermode="closest")
            st.plotly_chart(fig, use_container_width=True, key=f"detail_engagement_compare_{student_id}_{quarter}")


def _student_consistency_detail_data(
    raw: dict,
    student_id: int,
    module: str,
    presentation: str,
    start_week: int,
    end_week: int,
):
    cohort = _cohort_info(raw, module, presentation)
    course = _prepare_vle(raw, module, presentation)
    if cohort.empty or course.empty:
        return pd.DataFrame(), {}
    ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique())
    weeks = pd.Index(range(start_week, end_week + 1), name="week")
    current = course[course["week"].between(start_week, end_week)].copy()
    grouped = current.groupby(["id_student", "week"])["sum_click"].sum()
    full_index = pd.MultiIndex.from_product([ids, weeks], names=["id_student", "week"])
    active = grouped.reindex(full_index, fill_value=0.0).gt(0).astype(float)
    try:
        mine = active.xs(int(student_id), level="id_student").reindex(weeks, fill_value=0.0)
    except KeyError:
        mine = pd.Series(0.0, index=weeks)
    cumulative = mine.cumsum() / pd.Series(range(1, len(weeks) + 1), index=weeks) * 100.0
    progress = pd.DataFrame({"week": weeks, "Cumulative Active Weeks %": cumulative.to_numpy()})
    class_per_student = active.groupby(level="id_student").mean() * 100.0
    summary = {
        "student_pct": float(mine.mean() * 100.0) if len(mine) else 0.0,
        "class_pct": float(class_per_student.mean()) if not class_per_student.empty else 0.0,
        "active_weeks": int(mine.sum()),
        "quarter_weeks": int(len(weeks)),
        "inactive_weeks": [int(w) for w, value in mine.items() if value == 0],
    }
    return progress, summary


def _render_student_consistency_detail(raw, student_id, module, presentation, start_week, end_week, quarter):
    progress, summary = _student_consistency_detail_data(raw, student_id, module, presentation, start_week, end_week)
    left, right = st.columns(2)
    with left:
        st.markdown("#### My Study Consistency This Quarter")
        st.caption("Cumulative percentage of available weeks in which this learner has been active at least once.")
        if progress.empty:
            render_empty_state("Consistency unavailable", "Weekly activity could not be calculated.")
        else:
            fig = go.Figure(go.Scatter(
                x=progress["week"], y=progress["Cumulative Active Weeks %"], mode="lines+markers",
                name="Active Weeks So Far", line=dict(color="#4A78B6", width=3), marker=dict(size=7),
                hovertemplate="Week %{x}<br>Active weeks so far: %{y:.1f}%<extra></extra>",
            ))
            _base_figure_layout(fig, x_title="Course week", y_title="Active weeks so far (%)", height=330)
            fig.update_yaxes(range=[0, 105], ticksuffix="%")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig, use_container_width=True, key=f"detail_consistency_weekly_{student_id}_{quarter}")
    with right:
        st.markdown("#### ME vs Class Average")
        st.caption("Overall active-week percentage across the selected quarter.")
        if not summary:
            render_empty_state("Class comparison unavailable", "Quarter consistency could not be calculated.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=["Quarter consistency"], y=[summary["student_pct"]], name="ME", marker_color="#4A78B6", text=[f"{summary['student_pct']:.0f}%"], textposition="auto"))
            fig.add_trace(go.Bar(x=["Quarter consistency"], y=[summary["class_pct"]], name="Class Average", marker_color="#A8C8E8", text=[f"{summary['class_pct']:.0f}%"], textposition="auto"))
            _base_figure_layout(fig, y_title="Active weeks (%)", height=330)
            fig.update_layout(barmode="group")
            fig.update_yaxes(range=[0, 105], ticksuffix="%")
            st.plotly_chart(fig, use_container_width=True, key=f"detail_consistency_compare_{student_id}_{quarter}")
    if summary:
        if summary["inactive_weeks"]:
            gaps = ", ".join(f"Week {w}" for w in summary["inactive_weeks"])
            st.info(
                f"Active in **{summary['active_weeks']} of {summary['quarter_weeks']} weeks** ({summary['student_pct']:.0f}%). "
                f"Class Average: **{summary['class_pct']:.0f}%** active weeks. No activity was recorded in {gaps}."
            )
        else:
            st.success(
                f"Active in **all {summary['quarter_weeks']} weeks** this quarter. Class Average: **{summary['class_pct']:.0f}%** active weeks."
            )


def _student_assessment_detail(
    raw: dict,
    student_id: int,
    assessment_metrics: pd.DataFrame,
    score_distribution: pd.DataFrame,
    end_week: int,
):
    """Checkpoint-safe student assessment table plus useful summary fields."""
    if assessment_metrics.empty:
        return pd.DataFrame(), {}
    due = assessment_metrics.copy()
    student_scores = score_distribution[
        pd.to_numeric(score_distribution.get("id_student"), errors="coerce").eq(int(student_id))
    ].copy() if not score_distribution.empty else pd.DataFrame()

    cols = ["id_assessment", "score", "date_submitted", "date"]
    mine = student_scores[[c for c in cols if c in student_scores.columns]].copy() if not student_scores.empty else pd.DataFrame(columns=cols)
    details = due.merge(mine, on="id_assessment", how="left", suffixes=("", "_student"))
    if "date_student" in details.columns:
        details["due_date"] = pd.to_numeric(details["date"], errors="coerce")
    else:
        details["due_date"] = pd.to_numeric(details["date"], errors="coerce")
    details["date_submitted"] = pd.to_numeric(details.get("date_submitted"), errors="coerce")
    details["score"] = pd.to_numeric(details.get("score"), errors="coerce")
    details["Due Week"] = (details["due_date"] / 7.0).apply(lambda x: int(math.ceil(x)) if pd.notna(x) else None)
    details["Submitted Week"] = (details["date_submitted"] / 7.0).apply(lambda x: int(math.ceil(x)) if pd.notna(x) else None)

    def _timing(row):
        if pd.isna(row.get("date_submitted")):
            return "Not submitted by checkpoint"
        delta = int(round(float(row["due_date"] - row["date_submitted"])))
        if delta > 0:
            return f"{delta} day{'s' if delta != 1 else ''} early"
        if delta == 0:
            return "On deadline"
        late = abs(delta)
        return f"{late} day{'s' if late != 1 else ''} late"

    details["Timing"] = details.apply(_timing, axis=1)
    submitted = details["date_submitted"].notna()
    on_time = submitted & details["date_submitted"].le(details["due_date"])
    avg_score = details.loc[details["score"].notna(), "score"].mean()
    summary = {
        "submitted": int(submitted.sum()),
        "due": int(len(details)),
        "on_time": int(on_time.sum()),
        "avg_score": float(avg_score) if pd.notna(avg_score) else None,
        "missing": details.loc[~submitted, "Assessment"].tolist(),
    }
    return details, summary


def _render_student_assessment_progress(details: pd.DataFrame, student_id: int, quarter: str):
    st.markdown("#### My Assessment Progress")
    scored = details.dropna(subset=["score"]) if not details.empty else pd.DataFrame()
    if scored.empty:
        render_empty_state("Assessment progress unavailable", "No submitted assessment score is available by this checkpoint.")
        return
    fig = go.Figure(go.Scatter(
        x=scored["Assessment"], y=scored["score"], mode="lines+markers", name="Student score",
        line=dict(color="#4A78B6", width=3), marker=dict(size=8),
        hovertemplate="%{x}<br>Score: %{y:.1f}%<extra></extra>",
    ))
    _base_figure_layout(fig, x_title="Assessment", y_title="Score (%)", height=330)
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True, key=f"detail_assessment_progress_{student_id}_{quarter}")


# -----------------------------------------------------------------------------
# Global Admin helpers
# -----------------------------------------------------------------------------

def _programme_context():
    """Programme controls for the held-out analytics scope."""
    with ribbon_start("Programme context"):
        c1, c2 = st.columns([4.2, 2.0])
        with c1:
            st.text_input(
                "Scope",
                value="Held-out programme data",
                disabled=True,
                key="admin_global_scope",
            )
        with c2:
            quarter = st.selectbox(
                "Programme checkpoint",
                QUARTER_ORDER,
                format_func=lambda q: QUARTER_LABELS.get(q, q),
                index=1,
                key="admin_quarter",
            )
    return quarter

def _prepare_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary is None or summary.empty:
        return pd.DataFrame()
    out = summary.copy()
    keys = [
        c for c in ["id_student", "code_module", "code_presentation"]
        if c in out.columns
    ]
    if len(keys) == 3:
        out = out.drop_duplicates(keys, keep="last")
    out["Support Status"] = out.apply(_normalise_support, axis=1)
    return out


def _evaluation_pairs(summary: pd.DataFrame) -> pd.DataFrame:
    """Module-presentations represented by the evaluation recommendation export.

    This is the single source of truth for Admin analytics scope.  Raw OULAD tables
    are never allowed to widen the dashboard back to training/earlier presentations.
    """
    required = {"code_module", "code_presentation"}
    if summary is None or summary.empty or not required.issubset(summary.columns):
        return pd.DataFrame(columns=["code_module", "code_presentation"])

    pairs = summary[["code_module", "code_presentation"]].dropna().copy()
    pairs["code_module"] = pairs["code_module"].astype(str).str.strip()
    pairs["code_presentation"] = pairs["code_presentation"].astype(str).str.strip()
    return pairs.drop_duplicates().sort_values(
        ["code_module", "code_presentation"]
    ).reset_index(drop=True)


def _evaluation_members(summary: pd.DataFrame) -> pd.DataFrame:
    """Exact evaluation learner-course memberships when student IDs are available."""
    required = {"id_student", "code_module", "code_presentation"}
    if summary is None or summary.empty or not required.issubset(summary.columns):
        return pd.DataFrame(columns=["id_student", "code_module", "code_presentation"])

    members = summary[["id_student", "code_module", "code_presentation"]].dropna().copy()
    members["id_student"] = pd.to_numeric(members["id_student"], errors="coerce")
    members = members.dropna(subset=["id_student"]).copy()
    members["id_student"] = members["id_student"].astype(int)
    members["code_module"] = members["code_module"].astype(str).str.strip()
    members["code_presentation"] = members["code_presentation"].astype(str).str.strip()
    return members.drop_duplicates().reset_index(drop=True)


def _filter_to_evaluation_members(
    frame: pd.DataFrame,
    evaluation_members: pd.DataFrame,
    evaluation_pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Prefer exact learner-course evaluation membership; otherwise restrict by pair."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=frame.columns if isinstance(frame, pd.DataFrame) else None)

    member_keys = {"id_student", "code_module", "code_presentation"}
    if (
        evaluation_members is not None
        and not evaluation_members.empty
        and member_keys.issubset(frame.columns)
    ):
        work = frame.copy()
        work["id_student"] = pd.to_numeric(work["id_student"], errors="coerce")
        work = work.dropna(subset=["id_student"]).copy()
        work["id_student"] = work["id_student"].astype(int)
        work["code_module"] = work["code_module"].astype(str).str.strip()
        work["code_presentation"] = work["code_presentation"].astype(str).str.strip()
        members = evaluation_members[list(member_keys)].drop_duplicates().copy()
        members["_evaluation_member"] = 1
        return (
            work.merge(
                members,
                on=["id_student", "code_module", "code_presentation"],
                how="inner",
            )
            .drop(columns="_evaluation_member")
        )

    return _filter_to_evaluation_scope(frame, evaluation_pairs)


def _evaluation_raw_tables(
    raw: dict,
    evaluation_members: pd.DataFrame,
    evaluation_pairs: pd.DataFrame,
) -> dict:
    """Return a copy of dashboard raw tables restricted to evaluation data."""
    scoped = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in raw.items()}

    for key in ["student_info", "student_vle"]:
        value = scoped.get(key, pd.DataFrame())
        if isinstance(value, pd.DataFrame):
            scoped[key] = _filter_to_evaluation_members(
                value, evaluation_members, evaluation_pairs
            )

    for key in ["courses", "assessments", "vle_meta"]:
        value = scoped.get(key, pd.DataFrame())
        if isinstance(value, pd.DataFrame) and {
            "code_module", "code_presentation"
        }.issubset(value.columns):
            scoped[key] = _filter_to_evaluation_scope(value, evaluation_pairs)

    sa = scoped.get("student_assessment", pd.DataFrame())
    if (
        isinstance(sa, pd.DataFrame)
        and not sa.empty
        and "id_student" in sa.columns
        and evaluation_members is not None
        and not evaluation_members.empty
    ):
        valid_ids = set(evaluation_members["id_student"].astype(int).tolist())
        sid = pd.to_numeric(sa["id_student"], errors="coerce")
        scoped["student_assessment"] = sa[sid.isin(valid_ids)].copy()

    return scoped


def _filter_to_evaluation_scope(
    frame: pd.DataFrame,
    evaluation_pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Restrict any raw table to the module-presentations in the evaluation set."""
    required = {"code_module", "code_presentation"}
    if (
        frame is None
        or frame.empty
        or evaluation_pairs is None
        or evaluation_pairs.empty
        or not required.issubset(frame.columns)
    ):
        return pd.DataFrame(columns=frame.columns if isinstance(frame, pd.DataFrame) else None)

    work = frame.copy()
    work["code_module"] = work["code_module"].astype(str).str.strip()
    work["code_presentation"] = work["code_presentation"].astype(str).str.strip()

    pairs = evaluation_pairs[["code_module", "code_presentation"]].drop_duplicates().copy()
    pairs["code_module"] = pairs["code_module"].astype(str).str.strip()
    pairs["code_presentation"] = pairs["code_presentation"].astype(str).str.strip()
    pairs["_evaluation_scope"] = 1

    return (
        work.merge(pairs, on=["code_module", "code_presentation"], how="inner")
        .drop(columns="_evaluation_scope")
    )


def _programme_engagement_data(
    raw: dict,
    evaluation_pairs: pd.DataFrame,
    quarter: str,
) -> pd.DataFrame:
    """Weekly overall engagement by module within the held-out analytics scope.

    If more than one included presentation exists for a module, the module line is
    weighted by the number of learners in each presentation so that large and small
    cohorts are not treated as equally sized.
    """
    if evaluation_pairs is None or evaluation_pairs.empty:
        return pd.DataFrame()

    rows = []
    for _, pair in evaluation_pairs.iterrows():
        module = str(pair["code_module"])
        presentation = str(pair["code_presentation"])
        course_weeks = _course_weeks(raw, module, presentation)
        start_week, end_week = _quarter_bounds(course_weeks, quarter)
        weekly, stats = _class_weekly_metrics(
            raw, module, presentation, start_week, end_week
        )
        class_size = int(stats.get("class_size", 0) or 0)
        if weekly.empty or class_size <= 0 or "Overall Engagement" not in weekly.columns:
            continue

        for _, row in weekly.iterrows():
            overall = _safe_number(row.get("Overall Engagement"), 0.0) or 0.0
            active_pct = _safe_number(row.get("Students Active (%)"), 0.0) or 0.0
            rows.append({
                "Module": module,
                "Presentation": presentation,
                "week": int(row["week"]),
                "_learners": class_size,
                "_engagement_total": float(overall) * class_size,
                "_active_students": float(active_pct) / 100.0 * class_size,
            })

    if not rows:
        return pd.DataFrame()

    grouped = pd.DataFrame(rows).groupby(["Module", "week"], as_index=False).agg(
        _learners=("_learners", "sum"),
        _engagement_total=("_engagement_total", "sum"),
        _active_students=("_active_students", "sum"),
    )
    grouped["Overall Engagement"] = (
        grouped["_engagement_total"]
        / grouped["_learners"].where(grouped["_learners"].gt(0))
    )
    grouped["Students Active (%)"] = (
        grouped["_active_students"]
        / grouped["_learners"].where(grouped["_learners"].gt(0))
        * 100.0
    )
    return grouped[[
        "Module", "week", "Overall Engagement", "Students Active (%)"
    ]].sort_values(["Module", "week"])


def _render_programme_engagement(
    raw: dict,
    evaluation_pairs: pd.DataFrame,
    quarter: str,
):
    """Render one overall-engagement line per module."""
    weekly = _programme_engagement_data(raw, evaluation_pairs, quarter)
    if weekly.empty:
        render_empty_state(
            "Programme engagement unavailable",
            "VLE data are required to build the programme engagement trend.",
        )
        return

    st.markdown("#### Overall engagement by module")
    st.caption(
        "Each line shows average VLE interactions per enrolled learner for one module "
        "during the selected checkpoint. Detailed course and presentation engagement "
        "is available in the Course & Presentation Comparison tab."
    )

    fig = go.Figure()
    for module in sorted(weekly["Module"].dropna().astype(str).unique()):
        sub = weekly[weekly["Module"].astype(str).eq(module)].sort_values("week")
        fig.add_trace(go.Scatter(
            x=sub["week"],
            y=sub["Overall Engagement"],
            mode="lines+markers",
            name=module,
            line=dict(width=2.6),
            marker=dict(size=6),
            hovertemplate=(
                "Module " + module
                + "<br>Course week %{x}"
                + "<br>Average interactions per learner: %{y:.1f}<extra></extra>"
            ),
        ))

    _base_figure_layout(
        fig,
        x_title="Course week",
        y_title="Average interactions per learner",
        height=390,
    )
    fig.update_layout(
        legend=dict(
            title="Module",
            orientation="h",
            y=1.12,
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=55, b=10),
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"admin_programme_engagement_by_module_{quarter}",
    )


def _course_engagement_summary(
    raw: dict,
    evaluation_pairs: pd.DataFrame,
    quarter: str,
) -> pd.DataFrame:
    """Course-wise engagement summary restricted to evaluation presentations."""
    if evaluation_pairs is None or evaluation_pairs.empty:
        return pd.DataFrame()

    rows = []
    for _, pair in evaluation_pairs.iterrows():
        module = str(pair["code_module"])
        presentation = str(pair["code_presentation"])
        course_weeks = _course_weeks(raw, module, presentation)
        start_week, end_week = _quarter_bounds(course_weeks, quarter)
        weekly, stats = _class_weekly_metrics(
            raw, module, presentation, start_week, end_week
        )
        if weekly.empty:
            continue
        rows.append({
            "Module": module,
            "Presentation": presentation,
            "Learners": int(stats.get("class_size", 0) or 0),
            "Weeks": f"{start_week}–{end_week}",
            "Avg Weekly Engagement": float(
                pd.to_numeric(weekly["Overall Engagement"], errors="coerce").mean()
            ),
            "Avg Active Weeks %": float(stats.get("mean_active_ratio", 0.0) or 0.0),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["Module", "Presentation"]
    ).reset_index(drop=True)


def _render_course_engagement_summary(
    raw: dict,
    evaluation_pairs: pd.DataFrame,
    quarter: str,
):
    course_engagement = _course_engagement_summary(raw, evaluation_pairs, quarter)
    st.markdown("### Course engagement comparison")
    st.caption(
        "Compare included course-presentations. Select a course below for its detailed "
        "weekly Content, Assessment, Social and Overall engagement view."
    )
    if course_engagement.empty:
        render_empty_state(
            "Course engagement comparison unavailable",
            "VLE data are required for course-wise engagement analytics.",
        )
        return

    display = course_engagement.copy()
    display["Avg Weekly Engagement"] = pd.to_numeric(
        display["Avg Weekly Engagement"], errors="coerce"
    ).round(1)
    display["Avg Active Weeks %"] = pd.to_numeric(
        display["Avg Active Weeks %"], errors="coerce"
    ).round(1)
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Avg Weekly Engagement": st.column_config.NumberColumn(format="%.1f"),
            "Avg Active Weeks %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def _programme_student_support_counts(summary: pd.DataFrame) -> dict:
    """One programme status per learner: the highest-touch status wins."""
    counts = {level: 0 for level in SUPPORT_ORDER}
    if summary is None or summary.empty or "Support Status" not in summary.columns:
        return counts
    if "id_student" not in summary.columns:
        vc = summary["Support Status"].value_counts()
        return {level: int(vc.get(level, 0)) for level in SUPPORT_ORDER}

    severity = {"On Track": 0, "Needs Attention": 1, "Priority Support": 2}
    tmp = summary[["id_student", "Support Status"]].copy()
    tmp["id_student"] = pd.to_numeric(tmp["id_student"], errors="coerce")
    tmp = tmp.dropna(subset=["id_student"])
    tmp["_severity"] = tmp["Support Status"].map(severity).fillna(1)
    worst = (
        tmp.sort_values("_severity")
        .groupby("id_student", as_index=False)
        .tail(1)["Support Status"]
        .value_counts()
    )
    return {level: int(worst.get(level, 0)) for level in SUPPORT_ORDER}


def _course_presentation_breakdown(summary: pd.DataFrame) -> pd.DataFrame:
    required = {"code_module", "code_presentation", "Support Status"}
    if summary is None or summary.empty or not required.issubset(summary.columns):
        return pd.DataFrame()

    rows = []
    for (module, presentation), grp in summary.groupby(
        ["code_module", "code_presentation"], dropna=False
    ):
        n = len(grp)
        counts = grp["Support Status"].value_counts()
        on_track = int(counts.get("On Track", 0))
        attention = int(counts.get("Needs Attention", 0))
        priority = int(counts.get("Priority Support", 0))
        rows.append({
            "Module": str(module),
            "Presentation": str(presentation),
            "Learner enrolments": n,
            "On Track %": 100.0 * on_track / max(n, 1),
            "Needs Attention %": 100.0 * attention / max(n, 1),
            "Priority Support %": 100.0 * priority / max(n, 1),
            "Support Load %": 100.0 * (attention + priority) / max(n, 1),
            "Priority learners": priority,
        })
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["Priority Support %", "Support Load %", "Learner enrolments"],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )


def _population_by_module(info: pd.DataFrame) -> pd.DataFrame:
    required = {"id_student", "code_module", "code_presentation"}
    if info is None or info.empty or not required.issubset(info.columns):
        return pd.DataFrame()
    out = (
        info.dropna(subset=list(required))
        .groupby(["code_module", "code_presentation"])["id_student"]
        .nunique()
        .reset_index(name="Students")
    )
    out["code_module"] = out["code_module"].astype(str)
    out["code_presentation"] = out["code_presentation"].astype(str)
    return out


def _render_population_chart(info: pd.DataFrame):
    """Stacked module population with segment counts and module totals visible."""
    population = _population_by_module(info)
    if population.empty:
        render_empty_state(
            "Population view unavailable",
            "Student enrolment data are required to compare programme populations.",
        )
        return

    modules = sorted(population["code_module"].unique())
    presentations = sorted(population["code_presentation"].unique())
    totals = (
        population.groupby("code_module")["Students"].sum()
        .reindex(modules, fill_value=0)
        .astype(int)
    )

    fig = go.Figure()
    for presentation in presentations:
        sub = population[population["code_presentation"].eq(presentation)]
        lookup = sub.set_index("code_module")["Students"]
        values = [int(lookup.get(m, 0)) for m in modules]
        fig.add_trace(go.Bar(
            x=modules,
            y=values,
            name=str(presentation),
            text=[f"{v:,}" if v > 0 else "" for v in values],
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=(
                "Module %{x}<br>Presentation " + str(presentation) +
                "<br>%{y:,} students<extra></extra>"
            ),
        ))

    for module in modules:
        total = int(totals.get(module, 0))
        fig.add_annotation(
            x=module,
            y=total,
            text=f"<b>{total:,}</b>",
            showarrow=False,
            yshift=15,
            font=dict(size=12),
        )

    _base_figure_layout(
        fig,
        x_title="Module",
        y_title="Enrolled students",
        height=390,
    )
    fig.update_layout(
        barmode="stack",
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig, use_container_width=True, key="admin_population_modules")


def _raw_student_registration() -> pd.DataFrame:
    try:
        loaded = load_dashboard_data()
    except Exception:
        return pd.DataFrame()

    if isinstance(loaded, dict):
        for key in ("studentRegistration", "student_registration", "registration"):
            value = loaded.get(key)
            if isinstance(value, pd.DataFrame):
                return value.copy()
        return pd.DataFrame()

    if isinstance(loaded, (list, tuple)):
        if len(loaded) > 4 and isinstance(loaded[4], pd.DataFrame):
            candidate = loaded[4]
            if {"id_student", "code_module", "code_presentation"}.issubset(candidate.columns):
                return candidate.copy()
        for value in loaded:
            if not isinstance(value, pd.DataFrame):
                continue
            if {
                "id_student", "code_module", "code_presentation",
                "date_unregistration",
            }.issubset(value.columns):
                return value.copy()
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _dashboard_registration_context() -> pd.DataFrame:
    """Prefer the notebook's dashboard-only context export; fall back to raw data."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "data" / "dashboard_registration_context.parquet",
        here.parent.parent / "data" / "dashboard_registration_context.parquet",
        here.parent.parent.parent / "data" / "dashboard_registration_context.parquet",
    ]
    for path in candidates:
        try:
            if path.exists():
                frame = pd.read_parquet(path)
                if {
                    "id_student", "code_module", "code_presentation",
                    "date_unregistration",
                }.issubset(frame.columns):
                    return frame
        except Exception:
            continue

    reg = _raw_student_registration()
    if reg.empty:
        return pd.DataFrame()

    reg = reg.copy()
    reg["date_registration"] = pd.to_numeric(reg.get("date_registration"), errors="coerce")
    reg["date_unregistration"] = pd.to_numeric(reg.get("date_unregistration"), errors="coerce")
    reg.loc[reg["date_unregistration"] < 0, "date_unregistration"] = pd.NA
    reg["registration_week"] = (reg["date_registration"] // 7 + 1).astype("Int64")
    reg["withdrawal_week"] = (reg["date_unregistration"] // 7 + 1).astype("Int64")

    raw = _load_raw_tables()
    courses = raw.get("courses", pd.DataFrame())
    if isinstance(courses, pd.DataFrame) and not courses.empty:
        rows = []
        for _, row in courses.drop_duplicates(["code_module", "code_presentation"]).iterrows():
            module = str(row.get("code_module"))
            presentation = str(row.get("code_presentation"))
            weeks = _course_weeks(raw, module, presentation)
            qends = []
            for q in QUARTER_ORDER:
                _, qend = _quarter_bounds(weeks, q)
                qends.append(qend)
            rows.append({
                "code_module": module,
                "code_presentation": presentation,
                "course_weeks": weeks,
                "q1_end": qends[0],
                "q2_end": qends[1],
                "q3_end": qends[2],
                "q4_end": qends[3],
            })
        windows = pd.DataFrame(rows)
        reg["code_module"] = reg["code_module"].astype(str)
        reg["code_presentation"] = reg["code_presentation"].astype(str)
        reg = reg.merge(
            windows,
            on=["code_module", "code_presentation"],
            how="left",
        )

    def event_quarter(row):
        week = row.get("withdrawal_week")
        if pd.isna(week) or int(week) < 1:
            return pd.NA
        week = int(week)
        for q, col in zip(QUARTER_ORDER, ["q1_end", "q2_end", "q3_end", "q4_end"]):
            end = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
            if pd.notna(end) and week <= int(end):
                return q
        return pd.NA

    if "withdrawal_quarter" not in reg.columns:
        reg["withdrawal_quarter"] = reg.apply(event_quarter, axis=1)
    return reg


def _withdrawal_timing_data(
    quarter: str,
    evaluation_members: pd.DataFrame,
    evaluation_pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Withdrawal events from evaluation learner-course memberships only."""
    ctx = _dashboard_registration_context()
    if ctx.empty or evaluation_pairs is None or evaluation_pairs.empty:
        return pd.DataFrame()

    out = _filter_to_evaluation_members(ctx, evaluation_members, evaluation_pairs)
    if out.empty:
        return pd.DataFrame()

    out["date_unregistration"] = pd.to_numeric(
        out.get("date_unregistration"), errors="coerce"
    )
    if "withdrawal_week" not in out.columns:
        out["withdrawal_week"] = (
            out["date_unregistration"] // 7 + 1
        ).astype("Int64")

    out = out[
        out["date_unregistration"].notna()
        & out["date_unregistration"].ge(0)
    ].copy()

    if "withdrawal_quarter" in out.columns:
        out = out[
            out["withdrawal_quarter"].astype(str).str.upper().eq(str(quarter).upper())
        ].copy()
    return out

def _withdrawal_course_presentation_summary(
    withdrawals: pd.DataFrame,
    info: pd.DataFrame,
) -> pd.DataFrame:
    """Summarise selected-quarter withdrawal events by module-presentation."""
    if withdrawals is None or withdrawals.empty:
        return pd.DataFrame()

    required = {"code_module", "code_presentation", "id_student", "withdrawal_week"}
    if not required.issubset(withdrawals.columns):
        return pd.DataFrame()

    work = withdrawals.copy()
    work["code_module"] = work["code_module"].astype(str)
    work["code_presentation"] = work["code_presentation"].astype(str)
    work["withdrawal_week"] = pd.to_numeric(work["withdrawal_week"], errors="coerce")
    work = work.dropna(subset=["withdrawal_week"]).copy()
    if work.empty:
        return pd.DataFrame()
    work["withdrawal_week"] = work["withdrawal_week"].astype(int)

    totals = (
        work.groupby(["code_module", "code_presentation"])
        .size()
        .reset_index(name="Withdrawal Events")
    )

    weekly = (
        work.groupby(["code_module", "code_presentation", "withdrawal_week"])
        .size()
        .reset_index(name="Week Withdrawals")
    )
    peak_idx = weekly.groupby(["code_module", "code_presentation"])["Week Withdrawals"].idxmax()
    peak = weekly.loc[peak_idx, [
        "code_module", "code_presentation", "withdrawal_week", "Week Withdrawals"
    ]].rename(columns={
        "withdrawal_week": "Peak Week",
        "Week Withdrawals": "Peak Week Events",
    })
    totals = totals.merge(peak, on=["code_module", "code_presentation"], how="left")

    # Population gives context for comparing differently sized course offerings.
    population = _population_by_module(info)
    if not population.empty:
        population = population.rename(columns={
            "code_module": "code_module",
            "code_presentation": "code_presentation",
            "Students": "Enrolled Students",
        })
        totals = totals.merge(
            population[["code_module", "code_presentation", "Enrolled Students"]],
            on=["code_module", "code_presentation"],
            how="left",
        )
    else:
        totals["Enrolled Students"] = pd.NA

    total_events = max(int(totals["Withdrawal Events"].sum()), 1)
    totals["Share of Quarter Withdrawals %"] = totals["Withdrawal Events"] / total_events * 100.0
    enrolled = pd.to_numeric(totals["Enrolled Students"], errors="coerce")
    totals["Withdrawal Rate %"] = (
        totals["Withdrawal Events"] / enrolled.where(enrolled.gt(0)) * 100.0
    )

    totals = totals.rename(columns={
        "code_module": "Module",
        "code_presentation": "Presentation",
    })
    return totals.sort_values(
        ["Withdrawal Events", "Withdrawal Rate %", "Module", "Presentation"],
        ascending=[False, False, True, True],
        na_position="last",
    ).reset_index(drop=True)


def _render_withdrawal_timing(
    quarter: str,
    info: pd.DataFrame,
    evaluation_members: pd.DataFrame,
    evaluation_pairs: pd.DataFrame,
):
    """Evaluation-cohort withdrawal overview with optional course drill-down."""
    withdrawals = _withdrawal_timing_data(quarter, evaluation_members, evaluation_pairs)
    if withdrawals.empty:
        render_empty_state(
            f"No withdrawals available for {quarter}",
            "No withdrawal events are recorded for the included course-presentations in this checkpoint.",
        )
        return

    required = {"code_module", "code_presentation", "withdrawal_week"}
    if not required.issubset(withdrawals.columns):
        render_empty_state(
            "Course-presentation withdrawal detail unavailable",
            "Registration data must contain module, presentation and withdrawal week.",
        )
        return

    withdrawals = withdrawals.copy()
    withdrawals["code_module"] = withdrawals["code_module"].astype(str)
    withdrawals["code_presentation"] = withdrawals["code_presentation"].astype(str)
    withdrawals["withdrawal_week"] = pd.to_numeric(
        withdrawals["withdrawal_week"], errors="coerce"
    )
    withdrawals = withdrawals.dropna(subset=["withdrawal_week"]).copy()
    withdrawals["withdrawal_week"] = withdrawals["withdrawal_week"].astype(int)

    if withdrawals.empty:
        render_empty_state(
            f"No withdrawals available for {quarter}",
            "No valid withdrawal weeks are available for this checkpoint.",
        )
        return

    summary = _withdrawal_course_presentation_summary(withdrawals, info)
    programme_weekly = withdrawals.groupby("withdrawal_week").size().sort_index()
    min_week = int(programme_weekly.index.min())
    max_week = int(programme_weekly.index.max())
    programme_weeks = list(range(min_week, max_week + 1))
    programme_values = [int(programme_weekly.get(week, 0)) for week in programme_weeks]

    total_withdrawals = int(len(withdrawals))
    peak_week = int(programme_weekly.idxmax())
    peak_events = int(programme_weekly.max())

    if not summary.empty:
        top = summary.iloc[0]
        top_label = f"{top['Module']} · {top['Presentation']}"
        top_value = f"{int(top['Withdrawal Events']):,}"
        top_subtitle = f"{float(top['Share of Quarter Withdrawals %']):.1f}% of {quarter} withdrawals"
    else:
        top_label = "Unavailable"
        top_value = "—"
        top_subtitle = "Course-presentation summary unavailable"

    k1, k2, k3 = st.columns(3)
    with k1:
        _metric_card(
            f"Total {quarter} withdrawals",
            f"{total_withdrawals:,}",
            "Withdrawal events in the current analytics scope",
        )
    with k2:
        _metric_card(
            "Peak withdrawal week",
            f"Week {peak_week}",
            f"{peak_events:,} withdrawal events in that week",
        )
    with k3:
        _metric_card(
            "Highest-withdrawal course",
            top_label,
            f"{top_value} events · {top_subtitle}",
        )

    st.markdown("#### Overall withdrawal pattern")
    st.caption(
        "Withdrawal events by course week across the included course-presentations. "
        "All modules are combined into one series here for readability."
    )

    programme_fig = go.Figure()
    programme_fig.add_trace(go.Bar(
        x=programme_weeks,
        y=programme_values,
        name="Withdrawals",
        marker_color="#6F94D0",
        text=[f"{v:,}" if v > 0 else "" for v in programme_values],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="Course week %{x}<br>%{y:,} withdrawal events<extra></extra>",
    ))
    _base_figure_layout(
        programme_fig,
        x_title="Course week",
        y_title="Withdrawal events",
        height=360,
    )
    programme_fig.update_layout(
        showlegend=False,
        uniformtext_minsize=9,
        uniformtext_mode="hide",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    programme_fig.update_xaxes(dtick=1)
    st.plotly_chart(
        programme_fig,
        use_container_width=True,
        key=f"admin_withdrawal_overall_{quarter}",
    )

    st.markdown("#### Explore by course & presentation")
    st.caption(
        "The filters contain only the course-presentations in the current analytics scope. The chart remains a "
        "single series at every drill-down level."
    )

    module_options = ["All modules"] + sorted(
        withdrawals["code_module"].dropna().astype(str).unique().tolist()
    )
    filter_left, filter_right = st.columns(2)
    with filter_left:
        selected_module = st.selectbox(
            "Module",
            module_options,
            index=0,
            key=f"admin_withdrawal_module_{quarter}",
        )

    if selected_module == "All modules":
        presentation_options = ["All presentations"]
    else:
        module_presentations = sorted(
            withdrawals.loc[
                withdrawals["code_module"].eq(selected_module),
                "code_presentation",
            ].dropna().astype(str).unique().tolist()
        )
        presentation_options = ["All presentations"] + module_presentations

    with filter_right:
        selected_presentation = st.selectbox(
            "Presentation",
            presentation_options,
            index=0,
            key=f"admin_withdrawal_presentation_{quarter}_{selected_module}",
            disabled=(selected_module == "All modules"),
        )

    if selected_module == "All modules":
        st.info(
            "Select a module above to open the course-level withdrawal view. "
            "The programme-level pattern is already shown above."
        )
    else:
        filtered = withdrawals[
            withdrawals["code_module"].eq(selected_module)
        ].copy()
        detail_label = selected_module

        if selected_presentation != "All presentations":
            filtered = filtered[
                filtered["code_presentation"].eq(selected_presentation)
            ].copy()
            detail_label = f"{selected_module} · {selected_presentation}"
        else:
            detail_label = f"{selected_module} · all included presentations"

        if filtered.empty:
            render_empty_state(
                "No withdrawals for this selection",
                f"No withdrawal events are available for {detail_label} during {quarter}.",
            )
        else:
            detail_weekly = filtered.groupby("withdrawal_week").size().sort_index()
            detail_min_week = int(detail_weekly.index.min())
            detail_max_week = int(detail_weekly.index.max())
            detail_weeks = list(range(detail_min_week, detail_max_week + 1))
            detail_values = [int(detail_weekly.get(week, 0)) for week in detail_weeks]
            detail_peak_week = int(detail_weekly.idxmax())
            detail_peak_events = int(detail_weekly.max())

            st.caption(
                f"**{detail_label}** — {len(filtered):,} withdrawal events in {quarter}; "
                f"peak at Week {detail_peak_week} ({detail_peak_events:,} events)."
            )

            detail_fig = go.Figure()
            detail_fig.add_trace(go.Bar(
                x=detail_weeks,
                y=detail_values,
                name=detail_label,
                marker_color="#4AAE9A",
                text=[f"{v:,}" if v > 0 else "" for v in detail_values],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    detail_label
                    + "<br>Course week %{x}<br>%{y:,} withdrawal events<extra></extra>"
                ),
            ))
            _base_figure_layout(
                detail_fig,
                x_title="Course week",
                y_title="Withdrawal events",
                height=330,
            )
            detail_fig.update_layout(
                showlegend=False,
                uniformtext_minsize=9,
                uniformtext_mode="hide",
                margin=dict(l=10, r=10, t=35, b=10),
            )
            detail_fig.update_xaxes(dtick=1)
            st.plotly_chart(
                detail_fig,
                use_container_width=True,
                key=(
                    f"admin_withdrawal_detail_{quarter}_"
                    f"{selected_module}_{selected_presentation}"
                ),
            )

    st.markdown("#### Withdrawal by module-presentation")
    st.caption(
        "Included course-presentations, sorted by selected-quarter withdrawal count. "
        "The table stays visible for precise comparison."
    )
    if not summary.empty:
        display = summary.copy()
        for col in ["Share of Quarter Withdrawals %", "Withdrawal Rate %"]:
            display[col] = pd.to_numeric(display[col], errors="coerce").round(1)
        display["Enrolled Students"] = pd.to_numeric(
            display["Enrolled Students"], errors="coerce"
        ).astype("Int64")

        def _highlight_top(row):
            return ["background-color: #FDECEC"] * len(row) if row.name == 0 else [""] * len(row)

        styled = display.style.apply(_highlight_top, axis=1)
        st.dataframe(
            styled,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Share of Quarter Withdrawals %": st.column_config.NumberColumn(format="%.1f%%"),
                "Withdrawal Rate %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

def _quarter_trend_data() -> pd.DataFrame:
    comparison = load_quarter_comparison()
    if comparison is None or comparison.empty:
        return pd.DataFrame()
    out = comparison.copy()
    quarter_col = "quarter" if "quarter" in out.columns else (
        "Quarter" if "Quarter" in out.columns else None
    )
    if quarter_col is None:
        return pd.DataFrame()
    out[quarter_col] = out[quarter_col].astype(str).str.upper()
    out = out[out[quarter_col].isin(QUARTER_ORDER)].copy()
    out["_order"] = out[quarter_col].map({q: i for i, q in enumerate(QUARTER_ORDER)})
    out = out.sort_values("_order").drop(columns="_order")
    if quarter_col != "quarter":
        out = out.rename(columns={quarter_col: "quarter"})
    return out


def _priority_table(breakdown: pd.DataFrame):
    display = breakdown.copy()
    for col in [
        "On Track %", "Needs Attention %", "Priority Support %", "Support Load %",
    ]:
        display[col] = pd.to_numeric(display[col], errors="coerce").round(1)

    def highlight_priority(row):
        if row.name in (0, 1):
            return ["background-color: #FDECEC"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(highlight_priority, axis=1)
    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        column_config={
            "On Track %": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f%%"
            ),
            "Needs Attention %": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f%%"
            ),
            "Priority Support %": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f%%"
            ),
            "Support Load %": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f%%"
            ),
        },
    )
    if len(display) >= 2:
        st.caption(
            "The first two rows are highlighted in pastel red because they currently "
            "have the highest Priority Support / Support Load and should be reviewed first."
        )


# -----------------------------------------------------------------------------
# Instructor mirror inside Admin
# -----------------------------------------------------------------------------

def _render_course_instructor_mirror(
    module: str,
    presentation: str,
    quarter: str,
    raw_override: dict | None = None,
):
    raw = raw_override if isinstance(raw_override, dict) else _load_raw_tables()
    course_weeks = _course_weeks(raw, module, presentation)
    start_week, end_week = _quarter_bounds(course_weeks, quarter)
    end_day = end_week * 7

    summary = cohort_summary(module, presentation, quarter)
    queue = cohort_priority_table(module, presentation, quarter)
    issues = common_issues(module, presentation, quarter)
    weekly, weekly_stats = _class_weekly_metrics(
        raw, module, presentation, start_week, end_week
    )
    assessment_metrics, score_distribution, assessment_stats = _assessment_checkpoint(
        raw, module, presentation, end_week
    )
    learner_metrics = _student_quarter_metrics(
        raw, module, presentation, start_week, end_week, assessment_metrics
    )
    enriched_queue = _enrich_queue(queue, learner_metrics)
    cohort = _cohort_info(raw, module, presentation)

    st.markdown(
        f"<div class='tw-instructor-note'>Admin is viewing the same <b>{escape(quarter)}</b> "
        f"course analytics available to the instructor for "
        f"<b>{escape(str(module))} · {escape(str(presentation))}</b>: Weeks "
        f"<b>{start_week}–{end_week}</b>. Evidence is restricted to data available "
        f"by Day {end_day}.</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Class Overview", "Support Queue", "Assessments", "Student Detail"])

    with tabs[0]:
        st.subheader("Class Overview")
        st.caption(
            "Instructor-equivalent checkpoint view of support demand, engagement, "
            "consistency and assessment participation."
        )
        total = int(cohort["id_student"].nunique()) if not cohort.empty else (
            int(summary["id_student"].nunique())
            if isinstance(summary, pd.DataFrame)
            and not summary.empty
            and "id_student" in summary.columns
            else 0
        )

        if isinstance(summary, pd.DataFrame) and not summary.empty:
            status_source = summary.copy()
            status_source["Support Status"] = status_source.apply(
                _normalise_support, axis=1
            )
        else:
            status_source = enriched_queue

        counts = {level: 0 for level in SUPPORT_META}
        if not status_source.empty and "Support Status" in status_source.columns:
            vc = status_source["Support Status"].value_counts()
            for level in counts:
                counts[level] = int(vc.get(level, 0))

        active_avg = weekly_stats.get("mean_active_ratio")
        submission_rate = assessment_stats.get("submission_rate")
        avg_score = assessment_stats.get("avg_score")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _metric_card("Learners", f"{total:,}", f"{module} · {presentation}")
        with c2:
            _support_card(
                "On Track", str(counts["On Track"]),
                "Continue normal monitoring", "On Track"
            )
        with c3:
            _support_card(
                "Needs Attention", str(counts["Needs Attention"]),
                "Timely behavioural support", "Needs Attention"
            )
        with c4:
            _support_card(
                "Priority Support", str(counts["Priority Support"]),
                "Prioritise instructor follow-up", "Priority Support"
            )

        c5, c6, c7 = st.columns(3)
        with c5:
            _metric_card(
                "Average Active Weeks",
                f"{active_avg:.0f}%" if active_avg is not None else "—",
                f"Across Weeks {start_week}–{end_week}",
            )
        with c6:
            _metric_card(
                "Assessment Submission",
                f"{submission_rate:.0f}%" if submission_rate is not None else "—",
                "Of assessment opportunities due by checkpoint",
            )
        with c7:
            _metric_card(
                "Average Available Score",
                f"{avg_score:.1f}%" if avg_score is not None else "—",
                "Submitted work available by checkpoint",
            )

        st.markdown("### Cohort engagement and consistency")
        col_eng, col_cons = st.columns([1.65, 1])
        with col_eng:
            st.markdown("**Average weekly engagement**")
            st.caption(
                "Class average interactions per enrolled learner; zero-activity "
                "learners remain in the denominator."
            )
            if weekly.empty:
                render_empty_state(
                    "Weekly engagement unavailable",
                    "Raw VLE data are not available for this cohort.",
                )
            else:
                fig = go.Figure()
                if weekly_stats.get("dimensions_available"):
                    colors = {
                        "Course Materials": "#3F72B5",
                        "Practice & Assessments": "#75B7E8",
                        "Learning With Others": "#8E6DB3",
                        "Overall Engagement": "#D98C8C",
                    }
                    for name in [
                        "Course Materials", "Practice & Assessments",
                        "Learning With Others", "Overall Engagement",
                    ]:
                        if name in weekly.columns:
                            fig.add_trace(go.Scatter(
                                x=weekly["week"],
                                y=weekly[name],
                                mode="lines+markers",
                                name=name,
                                line=dict(width=2.4, color=colors[name]),
                                marker=dict(size=5),
                            ))
                else:
                    fig.add_trace(go.Scatter(
                        x=weekly["week"],
                        y=weekly["Overall Engagement"],
                        mode="lines+markers",
                        name="Overall Engagement",
                        line=dict(width=2.6, color="#3F72B5"),
                    ))
                _base_figure_layout(
                    fig,
                    x_title="Course week",
                    y_title="Average interactions per learner",
                    height=350,
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"admin_class_engagement_{module}_{presentation}_{quarter}",
                )

        with col_cons:
            st.markdown("**Students active each week**")
            st.caption(
                "Percentage of enrolled learners with at least one VLE interaction "
                "in each week."
            )
            if weekly.empty or "Students Active (%)" not in weekly.columns:
                render_empty_state(
                    "Consistency trend unavailable",
                    "Raw VLE data are not available for this cohort.",
                )
            else:
                fig = go.Figure(go.Bar(
                    x=weekly["week"],
                    y=weekly["Students Active (%)"],
                    hovertemplate=(
                        "Week %{x}<br>Students active: %{y:.1f}%<extra></extra>"
                    ),
                ))
                _base_figure_layout(
                    fig,
                    x_title="Course week",
                    y_title="Students active (%)",
                    height=350,
                )
                fig.update_yaxes(range=[0, 100])
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"admin_class_consistency_{module}_{presentation}_{quarter}",
                )

        st.markdown("### Behavioural support demand")
        col_issue, col_first = st.columns([1.2, 1])
        with col_issue:
            if issues is None or issues.empty:
                render_empty_state(
                    "Cohort behavioural insights unavailable",
                    "Recommendation details are needed to aggregate common learning opportunities.",
                )
            else:
                top = issues.head(7).copy()
                fig = go.Figure(go.Bar(
                    x=top["Prevalence"],
                    y=top["issue_label"],
                    orientation="h",
                    hovertemplate="%{y}<br>%{x:.1f}% of learners<extra></extra>",
                ))
                _base_figure_layout(
                    fig,
                    x_title="Learners with this opportunity (%)",
                    y_title="",
                    height=330,
                )
                fig.update_layout(showlegend=False)
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"admin_cohort_issues_{module}_{presentation}_{quarter}",
                )
                st.caption(
                    "A common issue may indicate a course-level teaching opportunity "
                    "rather than an individual deficit."
                )
        with col_first:
            st.markdown("**Attention first**")
            st.caption(
                "Top learners from the behavioural recommendation priority queue."
            )
            ordered = (
                enriched_queue.sort_values(["Support Rank"], ascending=True)
                if not enriched_queue.empty
                else enriched_queue
            )
            _queue_table(ordered, compact=True)

    with tabs[1]:
        st.subheader("Support Queue")
        st.caption(
            "Same prioritisation context available to the instructor. Final academic "
            "outcomes remain excluded from operational support."
        )
        if enriched_queue.empty:
            render_empty_state(
                "Support queue unavailable",
                "Connect the recommendation exports to populate the action queue.",
            )
        else:
            legend_html = "<div class='tw-legend'>" + "".join(
                f"<span style='background:{meta['bg']};border-color:{meta['border']};"
                f"color:{meta['text']}'>{level}</span>"
                for level, meta in SUPPORT_META.items()
            ) + "</div>"
            st.markdown(legend_html, unsafe_allow_html=True)

            f1, f2, f3 = st.columns([1.35, 1.1, 1.4])
            with f1:
                status_filter = st.multiselect(
                    "Support status",
                    list(SUPPORT_META),
                    default=list(SUPPORT_META),
                    key=f"admin_status_filter_{module}_{presentation}_{quarter}",
                )
            with f2:
                student_search = st.text_input(
                    "Student ID",
                    placeholder="Search ID",
                    key=f"admin_student_search_{module}_{presentation}_{quarter}",
                )
            with f3:
                sort_by = st.selectbox(
                    "Sort",
                    [
                        "Support priority", "Lowest active weeks",
                        "Lowest engagement", "Most missed assessments",
                    ],
                    key=f"admin_queue_sort_{module}_{presentation}_{quarter}",
                )

            view = enriched_queue[
                enriched_queue["Support Status"].isin(status_filter)
            ].copy()
            if student_search.strip():
                view = view[
                    view["id_student"].astype(str).str.contains(
                        student_search.strip(), regex=False
                    )
                ]

            if sort_by == "Support priority":
                cols = ["Support Rank"]
                ascending = [True]
                if "max_gap_severity" in view.columns:
                    view["_gap"] = pd.to_numeric(
                        view["max_gap_severity"], errors="coerce"
                    ).fillna(-1)
                    cols.append("_gap")
                    ascending.append(False)
                view = view.sort_values(cols, ascending=ascending)
            elif sort_by == "Lowest active weeks" and "Active Weeks %" in view.columns:
                view = view.sort_values("Active Weeks %", ascending=True)
            elif sort_by == "Lowest engagement" and "Engagement vs Class %" in view.columns:
                view = view.sort_values("Engagement vs Class %", ascending=True)
            elif sort_by == "Most missed assessments" and {
                "Assessments Submitted", "Assessments Due",
            }.issubset(view.columns):
                view["_missed"] = (
                    pd.to_numeric(view["Assessments Due"], errors="coerce").fillna(0)
                    - pd.to_numeric(
                        view["Assessments Submitted"], errors="coerce"
                    ).fillna(0)
                )
                view = view.sort_values(
                    ["_missed", "Support Rank"], ascending=[False, True]
                )

            st.caption(
                f"Showing {len(view):,} learner records for the selected filters."
            )
            _queue_table(view)

    with tabs[2]:
        st.subheader("Assessments")
        st.caption(
            f"Same instructor assessment view available by {quarter}; submissions "
            f"after Day {end_day} remain excluded."
        )
        due_count = assessment_stats.get("due_count", 0)
        submission_rate = assessment_stats.get("submission_rate")
        not_submitted = assessment_stats.get("not_submitted", 0)
        avg_score = assessment_stats.get("avg_score")

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            _metric_card("Assessments Due", str(due_count), f"By Week {end_week}")
        with a2:
            _metric_card(
                "Submission Rate",
                f"{submission_rate:.0f}%" if submission_rate is not None else "—",
                "Across all due assessment opportunities",
            )
        with a3:
            _metric_card(
                "Not Submitted",
                f"{int(not_submitted):,}",
                "Student-assessment opportunities",
            )
        with a4:
            _metric_card(
                "Average Available Score",
                f"{avg_score:.1f}%" if avg_score is not None else "—",
                "Among submitted work by checkpoint",
            )

        st.markdown("### Class score distribution")
        _assessment_boxplot(
            score_distribution,
            key=f"admin_assessment_box_{module}_{presentation}_{quarter}",
        )

        st.markdown("### Submission and timing overview")
        if assessment_metrics.empty:
            render_empty_state(
                "No assessments due yet",
                "No assessment with a recorded due date falls before this checkpoint.",
            )
        else:
            display = assessment_metrics.copy()
            display["Due week"] = (
                pd.to_numeric(display["date"], errors="coerce") / 7.0
            ).apply(
                lambda x: int(math.ceil(x)) if pd.notna(x) else None
            )
            display["Weight (%)"] = pd.to_numeric(
                display.get("weight"), errors="coerce"
            )
            display["Average score (%)"] = pd.to_numeric(
                display["Average score (%)"], errors="coerce"
            ).round(1)
            display["Submission rate (%)"] = pd.to_numeric(
                display["Submission rate (%)"], errors="coerce"
            ).round(1)
            display = display[[
                "Assessment", "Due week", "Weight (%)", "Submitted",
                "Submission rate (%)", "Not submitted", "Late",
                "Average score (%)",
            ]]
            st.dataframe(
                display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Submission rate (%)": st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%.1f%%"
                    ),
                    "Average score (%)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                },
            )

    with tabs[3]:
        _render_admin_student_mirror(
            raw=raw,
            summary=summary,
            enriched_queue=enriched_queue,
            cohort=cohort,
            module=module,
            presentation=presentation,
            quarter=quarter,
            course_weeks=course_weeks,
            start_week=start_week,
            end_week=end_week,
            assessment_metrics=assessment_metrics,
            score_distribution=score_distribution,
        )


def _render_admin_student_mirror(
    *,
    raw: dict,
    summary: pd.DataFrame,
    enriched_queue: pd.DataFrame,
    cohort: pd.DataFrame,
    module: str,
    presentation: str,
    quarter: str,
    course_weeks: int,
    start_week: int,
    end_week: int,
    assessment_metrics: pd.DataFrame,
    score_distribution: pd.DataFrame,
):
    st.subheader("Student Detail")
    st.caption(
        "Student-facing information for the selected learner. The Admin can inspect "
        "the same learning indicators, assessments and recommendations but does not "
        "act on the student's behalf."
    )

    queue_ids = (
        set(enriched_queue["id_student"].astype(int).tolist())
        if not enriched_queue.empty else set()
    )
    cohort_ids = (
        set(pd.to_numeric(cohort["id_student"], errors="coerce")
            .dropna().astype(int).tolist())
        if not cohort.empty else set()
    )
    student_ids = sorted(queue_ids | cohort_ids)
    if not student_ids:
        render_empty_state(
            "Student profiles unavailable",
            "No learner records are available for this module-presentation.",
        )
        return

    student_id = st.selectbox(
        "Inspect student",
        student_ids,
        format_func=lambda sid: f"Student {sid}",
        key=f"admin_detail_student_{module}_{presentation}_{quarter}",
    )

    info = load_student_info()
    queue_row = {}
    if not enriched_queue.empty:
        match = enriched_queue[enriched_queue["id_student"].eq(int(student_id))]
        if not match.empty:
            queue_row = match.iloc[0].to_dict()
    if (
        not queue_row
        and isinstance(summary, pd.DataFrame)
        and not summary.empty
        and "id_student" in summary.columns
    ):
        sid = pd.to_numeric(summary["id_student"], errors="coerce")
        match = summary[sid.eq(int(student_id))]
        if not match.empty:
            queue_row = match.iloc[0].to_dict()

    level = _normalise_support(queue_row) if queue_row else "Needs Attention"
    pattern = student_learning_pattern(
        student_id, module, presentation, quarter
    )
    tiles = student_behaviour_tiles(
        student_id, module, presentation, quarter
    )
    recs = student_recommendations(
        student_id, module, presentation, quarter, limit=3
    )
    strengths, opportunities = student_strengths_opportunities(tiles)
    pred = prediction_for_student(
        student_id, module, presentation, quarter
    )
    opportunity = _first_existing(
        queue_row,
        ["Main opportunity", "main_opportunity", "primary_opportunity"],
        opportunities[0] if opportunities else "",
    )
    pattern_label = (
        pattern.get("label", "Behavioural profile")
        if isinstance(pattern, dict)
        else "Behavioural profile"
    )

    st.markdown("### Student & Course Context")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _detail_context_card("Student ID", student_id)
    with c2:
        _detail_context_card("Module", module)
    with c3:
        _detail_context_card("Presentation", presentation)
    with c4:
        _detail_context_card(
            "Checkpoint", f"{quarter} · Weeks {start_week}–{end_week}"
        )

    profile = _student_row(info, student_id, module, presentation)
    st.markdown("### Student Details")
    demographic_items = [
        ("Gender", profile.get("gender", "—")),
        ("Age Band", profile.get("age_band", "—")),
        ("Highest Education", profile.get("highest_education", "—")),
        ("Region", profile.get("region", "—")),
        ("Studied Credits", profile.get("studied_credits", "—")),
        ("Previous Attempts", profile.get("num_of_prev_attempts", "—")),
        ("Course Length", f"{course_weeks} weeks"),
    ]
    for start_idx in range(0, len(demographic_items), 4):
        cols = st.columns(4)
        for col, (label, value) in zip(
            cols, demographic_items[start_idx:start_idx + 4]
        ):
            with col:
                _detail_context_card(label, value)

    _support_banner(student_id, level, pattern_label, str(opportunity))
    _render_priority_recommendation_block(recs, fallback_issue=str(opportunity))

    detail_tabs = st.tabs(["My Learning", "Assessments", "Recommendations"])

    with detail_tabs[0]:
        st.markdown("### Behavioural Learning Indicators")
        st.caption(
            "The same behavioural learning signals shown on the Student page."
        )
        _grouped_behaviour_cards(tiles)

        st.markdown("### What the learning pattern is telling the student")
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("**What is working well**")
            if strengths:
                for item in strengths[:3]:
                    st.markdown(f"✓ {escape(str(item))}")
            else:
                st.caption(
                    "No clear strength has surfaced yet at this checkpoint."
                )
        with s2:
            st.markdown("**What could improve**")
            if opportunities:
                for item in opportunities[:3]:
                    st.markdown(f"→ {escape(str(item))}")
            else:
                st.caption(
                    "No meaningful behavioural opportunity has surfaced."
                )

        st.divider()
        st.markdown("### Explore Student Progress")
        progress_view = st.radio(
            "Progress view",
            ["Engagement", "Consistency", "Assessment"],
            horizontal=True,
            label_visibility="collapsed",
            key=f"admin_detail_progress_{student_id}_{quarter}",
        )
        student_assessment_details, student_assessment_summary = (
            _student_assessment_detail(
                raw, student_id, assessment_metrics,
                score_distribution, end_week
            )
        )
        if progress_view == "Engagement":
            _render_student_engagement_detail(
                raw, student_id, module, presentation, quarter, course_weeks
            )
        elif progress_view == "Consistency":
            _render_student_consistency_detail(
                raw, student_id, module, presentation,
                start_week, end_week, quarter
            )
        else:
            a1, a2 = st.columns(2)
            with a1:
                _render_student_assessment_progress(
                    student_assessment_details, student_id, quarter
                )
            with a2:
                st.markdown("#### Student Score Within Class Distribution")
                _assessment_boxplot(
                    score_distribution,
                    student_id=student_id,
                    key=f"admin_detail_learning_box_{student_id}_{quarter}",
                )
            if student_assessment_summary.get("missing"):
                st.warning(
                    "**Assessment not submitted at this checkpoint:** "
                    + ", ".join(student_assessment_summary["missing"])
                )

    with detail_tabs[1]:
        st.markdown("### Student Assessments")
        st.caption(
            f"Assessment information available by Week {end_week}; later "
            "submissions and scores remain hidden."
        )
        student_assessment_details, student_assessment_summary = (
            _student_assessment_detail(
                raw, student_id, assessment_metrics,
                score_distribution, end_week
            )
        )
        if student_assessment_details.empty:
            render_empty_state(
                "Assessment information unavailable",
                "No assessment with a recorded due date is available by this checkpoint.",
            )
        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                _metric_card(
                    "Submitted",
                    f"{student_assessment_summary['submitted']} / "
                    f"{student_assessment_summary['due']}",
                    "Due by this checkpoint",
                )
            with m2:
                avg = student_assessment_summary.get("avg_score")
                _metric_card(
                    "Average Score",
                    f"{avg:.0f}%" if avg is not None else "—",
                    "Available submitted assessments",
                )
            with m3:
                _metric_card(
                    "On Time",
                    f"{student_assessment_summary['on_time']} / "
                    f"{student_assessment_summary['submitted']}",
                    "Submitted on or before deadline",
                )
            with m4:
                _metric_card(
                    "Not Submitted",
                    str(len(student_assessment_summary.get("missing", []))),
                    "At this checkpoint",
                )

            display = student_assessment_details.copy()
            display["Score %"] = pd.to_numeric(
                display["score"], errors="coerce"
            )
            display["Weight %"] = pd.to_numeric(
                display.get("weight"), errors="coerce"
            )
            display = display[[
                "Assessment", "assessment_type", "Due Week",
                "Submitted Week", "Timing", "Score %", "Weight %",
            ]].rename(columns={"assessment_type": "Type"})
            st.dataframe(
                display, hide_index=True, use_container_width=True
            )

            st.markdown("#### Submission Timing")
            timing = student_assessment_details.dropna(
                subset=["date_submitted"]
            ).copy()
            if not timing.empty:
                timing["Days before deadline"] = (
                    timing["due_date"] - timing["date_submitted"]
                )
                fig = go.Figure(go.Bar(
                    x=timing["Assessment"],
                    y=timing["Days before deadline"],
                    text=timing["Timing"],
                    textposition="auto",
                ))
                fig.add_hline(
                    y=0,
                    line_dash="dash",
                    line_color="#98A2B3",
                    annotation_text="Deadline",
                )
                _base_figure_layout(
                    fig,
                    x_title="Assessment",
                    y_title="Days before deadline",
                    height=330,
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"admin_detail_assessment_timing_{student_id}_{quarter}",
                )

            st.markdown("#### Class Score Distribution by Assessment")
            _assessment_boxplot(
                score_distribution,
                student_id=student_id,
                key=f"admin_detail_assessment_box_{student_id}_{quarter}",
            )

    with detail_tabs[2]:
        st.markdown("### Personalised Recommendations")
        st.caption(
            "The same behavioural recommendations available on the Student page. "
            "Admin access is read-only."
        )
        _recommendation_cards(recs, level)

        st.divider()
        st.markdown("### Tutor Check-in History")
        items = list_interventions(
            module=module, presentation=presentation
        )
        items = [
            item for item in (items or [])
            if str(item.get("learner", "")).endswith(str(student_id))
        ]
        if items:
            for item in items:
                st.markdown(
                    f"**{escape(str(item.get('action', 'Check-in')))}**  \n"
                    f"{escape(str(item.get('created_at', '')))} · "
                    f"{escape(str(item.get('status', '')))} · "
                    f"{escape(str(item.get('note') or 'No note'))}"
                )
        else:
            st.caption(
                "No tutor check-in has been recorded for this learner in this session."
            )

        with st.expander("Technical details", expanded=False):
            if pred and pred.get("probability") is not None:
                st.write(
                    f"Model probability: **{pred['probability']:.3f}**"
                )
                st.write(
                    f"Model: {pred.get('model_name') or 'Not supplied'} · "
                    f"Threshold: "
                    f"{pred.get('threshold') if pred.get('threshold') is not None else 'Not supplied'}"
                )
            else:
                st.write(
                    "Student-level prediction output is not connected yet. "
                    "The support profile is driven by the behavioural recommendation layer."
                )
            st.write(
                "final_result is deliberately excluded from this operational view."
            )


def _course_selector_for_admin(summary: pd.DataFrame, quarter: str):
    """Course selector sourced only from evaluation recommendation outputs."""
    source = summary
    if (
        source is None
        or source.empty
        or not {"code_module", "code_presentation"}.issubset(source.columns)
    ):
        render_empty_state(
            "Course drill-down unavailable",
            "Recommendation outputs with module and presentation identifiers are required.",
        )
        return None, None

    module_options = sorted(source["code_module"].dropna().astype(str).unique())
    c1, c2 = st.columns(2)
    with c1:
        module = st.selectbox(
            "Module",
            module_options,
            key=f"admin_drill_module_{quarter}",
        )
    presentation_options = sorted(
        source.loc[
            source["code_module"].astype(str).eq(module),
            "code_presentation",
        ].dropna().astype(str).unique()
    )
    with c2:
        presentation = st.selectbox(
            "Presentation",
            presentation_options,
            key=f"admin_drill_presentation_{quarter}_{module}",
        )
    return module, presentation

# -----------------------------------------------------------------------------
# Main Admin page
# -----------------------------------------------------------------------------

def render_admin_dashboard(user):
    require_role(user, "admin")
    _inject_admin_styles()

    render_page_heading(
        "Programme intelligence",
        (
            "Programme overview with course-level Instructor analytics "
            "and student-level learning detail available through drill-down."
        ),
    )

    quarter = _programme_context()
    summary = _prepare_summary(load_recommendation_summary(quarter))
    evaluation_pairs = _evaluation_pairs(summary)
    evaluation_members = _evaluation_members(summary)
    all_info = load_student_info()
    info = _filter_to_evaluation_members(all_info, evaluation_members, evaluation_pairs)
    raw = _load_raw_tables()
    evaluation_raw = _evaluation_raw_tables(raw, evaluation_members, evaluation_pairs)
    breakdown = _course_presentation_breakdown(summary)

    modules = (
        sorted(evaluation_pairs["code_module"].dropna().astype(str).unique())
        if not evaluation_pairs.empty else []
    )
    presentations = (
        sorted(evaluation_pairs["code_presentation"].dropna().astype(str).unique())
        if not evaluation_pairs.empty else []
    )

    st.caption(
        f"Viewing the **{quarter} checkpoint** across {len(evaluation_pairs):,} included "
        "module-presentation offerings. Training and earlier presentations are excluded "
        "from programme, engagement and withdrawal analytics."
    )

    if evaluation_pairs.empty:
        st.warning(
            "No included module-presentations were found in the recommendation summary "
            f"for {quarter}. Admin analytics will remain empty rather than falling back to training data."
        )

    tabs = st.tabs([
        "Programme Overview",
        "Course & Presentation Comparison",
        "Governance & Evidence",
    ])

    with tabs[0]:
        st.subheader("Programme Overview")
        st.caption(
            "Institution-level analytics for the selected checkpoint. Only the held-out "
            "programme scope is included; training and earlier presentations remain excluded."
        )

        enrolled_students = (
            int(pd.to_numeric(info["id_student"], errors="coerce").dropna().nunique())
            if isinstance(info, pd.DataFrame)
            and not info.empty
            and "id_student" in info.columns
            else 0
        )
        support_counts = _programme_student_support_counts(summary)
        n_course_presentations = int(len(evaluation_pairs))

        c1, c2, c3 = st.columns(3)
        with c1:
            _metric_card(
                "Learners",
                f"{enrolled_students:,}",
                "Unique learners in the current programme scope",
            )
        with c2:
            _metric_card(
                "Modules",
                f"{len(modules):,}",
                "Distinct modules in the current programme scope",
            )
        with c3:
            _metric_card(
                "Presentations",
                f"{n_course_presentations:,}",
                "Module-presentation offerings in the current programme scope",
            )

        s1, s2, s3 = st.columns(3)
        with s1:
            _support_card(
                "On Track",
                f"{support_counts['On Track']:,}",
                f"{quarter} behavioural support status",
                "On Track",
            )
        with s2:
            _support_card(
                "Needs Attention",
                f"{support_counts['Needs Attention']:,}",
                f"{quarter} behavioural support status",
                "Needs Attention",
            )
        with s3:
            _support_card(
                "Priority Support",
                f"{support_counts['Priority Support']:,}",
                f"{quarter} behavioural support status",
                "Priority Support",
            )

        st.markdown("### Programme population")
        st.caption(
            "Learner population across the included module-presentations. "
            "Training and earlier presentations are not included."
        )
        _render_population_chart(info)

        st.divider()
        st.markdown(f"### Engagement during {quarter}")
        _render_programme_engagement(evaluation_raw, evaluation_pairs, quarter)

        st.divider()
        st.markdown(f"### Withdrawals during {quarter}")
        st.caption(
            "Withdrawal analytics use the same programme scope as the rest of this page and "
            "include only events occurring in the selected checkpoint."
        )
        _render_withdrawal_timing(quarter, info, evaluation_members, evaluation_pairs)

    with tabs[1]:
        st.subheader("Course & Presentation Comparison")
        st.caption(
            "Compare course-level engagement and support demand, then select one course "
            "for the full Instructor-equivalent analytics."
        )

        _render_course_engagement_summary(evaluation_raw, evaluation_pairs, quarter)

        st.divider()
        if breakdown.empty:
            render_empty_state(
                "Module-presentation comparison unavailable",
                "Recommendation outputs are required to build the priority table.",
            )
        else:
            st.markdown("### Module-presentation priority table")
            _priority_table(breakdown)

        st.divider()
        st.markdown("### Course Analytics — Instructor View")
        module, presentation = _course_selector_for_admin(summary, quarter)
        if module is not None and presentation is not None:
            _render_course_instructor_mirror(
                module, presentation, quarter, raw_override=evaluation_raw
            )

    with tabs[2]:
        st.subheader("Human Oversight")
        st.caption(
            "Analytics support programme and teaching decisions; they do not replace human judgement."
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                "**TrackWise can**\n\n"
                "Surface behavioural support needs, aggregate programme demand, "
                "prioritise follow-up and suggest educational actions."
            )
        with c2:
            st.markdown(
                "**TrackWise does not**\n\n"
                "Grade learners, remove students, make disciplinary decisions, "
                "or replace educator judgement."
            )
        with c3:
            st.markdown(
                "**Operational data principle**\n\n"
                "Operational analytics use the held-out programme scope and checkpoint-available "
                "learning behaviour. Final outcomes and future information are not used to assign support status."
            )

        st.divider()
        st.subheader("Research Evidence")
        comparison = _quarter_trend_data()
        if not comparison.empty:
            with st.expander("Recommendation comparison across Q1-Q4"):
                st.dataframe(
                    comparison,
                    hide_index=True,
                    use_container_width=True,
                )
        else:
            st.info(
                "The recommendation quarter-comparison export is not currently available."
            )

        st.markdown("### Research Boundary")
        st.write(
            "Admin operational analytics use only the held-out programme scope. "
            "The learner's final_result and information occurring after the selected checkpoint "
            "do not feed Student, Instructor or Admin support status. Withdrawal reporting is "
            "descriptive context and is filtered to the selected checkpoint."
        )

