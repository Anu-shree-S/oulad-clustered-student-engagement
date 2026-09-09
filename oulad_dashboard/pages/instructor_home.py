"""TrackWise Instructor Support Workspace.

Instructor-facing design principles:
- four operational tabs: Class Overview, Support Queue, Assessments, Student Detail;
- use quarter/checkpoint-safe evidence only (no future-course information);
- prioritise observable, modifiable learning behaviour over demographic risk labels;
- use the recommendation pipeline's support level as the operational status;
- never expose historical final_result in the instructor workflow;
- preserve human judgement: analytics support an instructor decision, they do not make it.
"""

from __future__ import annotations

from html import escape
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.permissions import assigned_modules, can_access_student, require_role
from components.layout import render_empty_state, render_page_heading, ribbon_start
from services.data_service import load_dashboard_data, load_student_info
from services.intervention_service import create_intervention, list_interventions, update_status
from services.learning_service import (
    QUARTER_LABELS,
    analytics_status,
    cohort_priority_table,
    cohort_summary,
    common_issues,
    prediction_for_student,
    student_behaviour_tiles,
    student_learning_pattern,
    student_recommendations,
    student_strengths_opportunities,
)


# -----------------------------------------------------------------------------
# Visual language
# -----------------------------------------------------------------------------

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


def _inject_styles():
    """Instructor-only styling; deliberately does not alter Student/Admin pages."""
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


# -----------------------------------------------------------------------------
# General helpers
# -----------------------------------------------------------------------------


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


def _course_selector(user):
    assignments = assigned_modules(user)
    if not assignments:
        st.error("No module-presentation is assigned to this instructor account.")
        st.stop()
    options = [f"{m} · {p}" for m, p in assignments]
    selected = st.selectbox("Course", options, key="instructor_course")
    return assignments[options.index(selected)]


def _normalise_support(row) -> str:
    """Map recommendation-layer wording onto the three instructor support levels."""
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
                is_relative = display_value == "Relative indicator"
                value_class = "value relative-indicator" if is_relative else "value"
                status_class = "status primary-status" if is_relative else "status"
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
        "Encourage the learner to start the next assessment several days earlier than usual and use the additional time to review instructions, ask questions and revise before submission."
    ),
    "deadline planning opportunity": (
        "Help the learner plan upcoming assessment deadlines in advance by setting an earlier personal reminder and breaking the work into smaller steps, reducing last-minute pressure."
    ),
    "assessment practice opportunity": (
        "Encourage the learner to complete at least one available quiz or self-check activity this week and use the result to identify topics that need further review."
    ),
    "course material engagement opportunity": (
        "Encourage the learner to reconnect with the core course materials before the next study or assessment session by reviewing the key resource for the upcoming topic and using it to guide practice."
    ),
    "study spacing opportunity": (
        "Encourage the learner to spread study across two or three shorter sessions on different days this week instead of concentrating activity into one long burst, reinforcing learning more regularly."
    ),
    "study consistency opportunity": (
        "Encourage the learner to build a steadier weekly routine by scheduling three small study windows this week—even 15–30 minutes each—so they stay connected to the course and prevent work from accumulating."
    ),
    "peer learning opportunity": (
        "Encourage the learner to participate in collaborative learning by reading the current discussion and contributing one question, reply or useful comment this week to test and clarify understanding."
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
            f"Support the learner in strengthening {focus} by agreeing one small, specific action to repeat consistently before the next checkpoint."
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


def _student_weekly_chart(raw: dict, student_id: int, module: str, presentation: str, start_week: int, end_week: int):
    cohort = _cohort_info(raw, module, presentation)
    course = _prepare_vle(raw, module, presentation)
    if cohort.empty or course.empty:
        render_empty_state("Engagement trend unavailable", "Raw VLE data are not available for this cohort.")
        return

    ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique())
    class_size = max(len(ids), 1)
    weeks = pd.Index(range(start_week, end_week + 1), name="week")
    current = course[course["week"].between(start_week, end_week)].copy()
    mine = current[current["id_student"].eq(int(student_id))]

    me_weekly = mine.groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0)
    class_weekly = current.groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0) / class_size

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks, y=class_weekly, mode="lines", name="Class Average",
        line=dict(color="#9AB8DC", width=2, dash="dot"),
        hovertemplate="Week %{x}<br>Class average: %{y:.0f} interactions<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=me_weekly, mode="lines+markers", name="Student",
        line=dict(color="#3F72B5", width=3), marker=dict(size=7),
        hovertemplate="Week %{x}<br>Student: %{y:.0f} interactions<extra></extra>",
    ))
    _base_figure_layout(fig, x_title="Course week", y_title="VLE interactions", height=320)
    st.plotly_chart(fig, use_container_width=True, key=f"instructor_student_engagement_{student_id}_{start_week}_{end_week}")


def _student_consistency_chart(raw_metrics: pd.DataFrame, student_id: int):
    if raw_metrics.empty or "Active Weeks %" not in raw_metrics.columns:
        render_empty_state("Consistency comparison unavailable", "Active-week data are not available for this checkpoint.")
        return
    row = raw_metrics[pd.to_numeric(raw_metrics["id_student"], errors="coerce").eq(int(student_id))]
    if row.empty:
        render_empty_state("Consistency comparison unavailable", "This learner is not present in the current cohort metrics.")
        return
    me = _safe_number(row.iloc[0].get("Active Weeks %"), 0.0) or 0.0
    class_avg = pd.to_numeric(raw_metrics["Active Weeks %"], errors="coerce").mean()
    class_avg = float(class_avg) if pd.notna(class_avg) else 0.0

    fig = go.Figure()
    fig.add_trace(go.Bar(x=["Active Weeks"], y=[me], name="Student", marker_color="#3F72B5", text=[f"{me:.0f}%"], textposition="inside"))
    fig.add_trace(go.Bar(x=["Active Weeks"], y=[class_avg], name="Class Average", marker_color="#93C5EE", text=[f"{class_avg:.0f}%"], textposition="inside"))
    _base_figure_layout(fig, x_title="", y_title="Active weeks (%)", height=300)
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True, key=f"instructor_student_consistency_{student_id}")


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



# -----------------------------------------------------------------------------
# Student-detail mirror of the Student dashboard
# -----------------------------------------------------------------------------


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
# Main page
# -----------------------------------------------------------------------------


def render_instructor_dashboard(user):
    require_role(user, "instructor")
    _inject_styles()

    render_page_heading(
        "Instructor support workspace",
        "Monitor the cohort, prioritise learners, understand the behaviour, and choose a human response.",
    )

    with ribbon_start("Cohort context"):
        c1, c2, c3 = st.columns([2.3, 2.2, 4])
        with c1:
            module, presentation = _course_selector(user)
        with c2:
            quarter = st.selectbox(
                "Course stage",
                list(QUARTER_LABELS),
                format_func=lambda q: QUARTER_LABELS[q],
                index=1,
                key="instructor_quarter",
            )
        with c3:
            analytics = analytics_status(quarter)
            connected = [
                name for name, ready in [
                    ("Behaviour", analytics.get("behaviour", False)),
                    ("Recommendations", analytics.get("recommendations", False)),
                    ("Prediction", analytics.get("predictions", False)),
                ] if ready
            ]
            st.text_input(
                "Connected analytics",
                value=" · ".join(connected) if connected else "Raw OULAD progress only",
                disabled=True,
                key="instructor_sources",
            )

    raw = _load_raw_tables()
    course_weeks = _course_weeks(raw, module, presentation)
    start_week, end_week = _quarter_bounds(course_weeks, quarter)
    end_day = end_week * 7

    summary = cohort_summary(module, presentation, quarter)
    queue = cohort_priority_table(module, presentation, quarter)
    issues = common_issues(module, presentation, quarter)
    weekly, weekly_stats = _class_weekly_metrics(raw, module, presentation, start_week, end_week)
    assessment_metrics, score_distribution, assessment_stats = _assessment_checkpoint(raw, module, presentation, end_week)
    learner_metrics = _student_quarter_metrics(raw, module, presentation, start_week, end_week, assessment_metrics)
    enriched_queue = _enrich_queue(queue, learner_metrics)
    cohort = _cohort_info(raw, module, presentation)

    st.markdown(
        f"<div class='tw-instructor-note'>Viewing <b>{escape(quarter)}</b> evidence for "
        f"<b>{escape(str(module))} · {escape(str(presentation))}</b>: course weeks "
        f"<b>{start_week}–{end_week}</b>. Raw behavioural and assessment summaries are restricted to data available by Day {end_day}.</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Class Overview", "Support Queue", "Assessments", "Student Detail"])

    # ------------------------------------------------------------------
    # 1. CLASS OVERVIEW
    # ------------------------------------------------------------------
    with tabs[0]:
        st.subheader("Class Overview")
        st.caption("A concise checkpoint view of support demand, engagement, consistency and assessment participation.")

        total = int(cohort["id_student"].nunique()) if not cohort.empty else (
            int(summary["id_student"].nunique()) if isinstance(summary, pd.DataFrame) and not summary.empty and "id_student" in summary.columns else 0
        )

        # Use the cohort summary for status counts when available because the
        # priority queue may intentionally contain only learners needing action.
        if isinstance(summary, pd.DataFrame) and not summary.empty:
            status_source = summary.copy()
            status_source["Support Status"] = status_source.apply(lambda r: _normalise_support(r), axis=1)
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
            _support_card("On Track", str(counts["On Track"]), "Continue normal monitoring", "On Track")
        with c3:
            _support_card("Needs Attention", str(counts["Needs Attention"]), "Timely behavioural support", "Needs Attention")
        with c4:
            _support_card("Priority Support", str(counts["Priority Support"]), "Prioritise instructor follow-up", "Priority Support")

        c5, c6, c7 = st.columns(3)
        with c5:
            _metric_card("Average Active Weeks", f"{active_avg:.0f}%" if active_avg is not None else "—", f"Across Weeks {start_week}–{end_week}")
        with c6:
            _metric_card("Assessment Submission", f"{submission_rate:.0f}%" if submission_rate is not None else "—", "Of assessment opportunities due by checkpoint")
        with c7:
            _metric_card("Average Available Score", f"{avg_score:.1f}%" if avg_score is not None else "—", "Submitted work available by checkpoint")

        st.markdown("### Cohort engagement and consistency")
        col_eng, col_cons = st.columns([1.65, 1])
        with col_eng:
            st.markdown("**Average weekly engagement**")
            st.caption("Class average interactions per enrolled learner; zero-activity learners remain in the denominator.")
            if weekly.empty:
                render_empty_state("Weekly engagement unavailable", "Raw VLE data are not available for this cohort.")
            else:
                fig = go.Figure()
                if weekly_stats.get("dimensions_available"):
                    colors = {
                        "Course Materials": "#3F72B5",
                        "Practice & Assessments": "#75B7E8",
                        "Learning With Others": "#8E6DB3",
                        "Overall Engagement": "#D98C8C",
                    }
                    for name in ["Course Materials", "Practice & Assessments", "Learning With Others", "Overall Engagement"]:
                        if name in weekly.columns:
                            fig.add_trace(go.Scatter(
                                x=weekly["week"], y=weekly[name], mode="lines+markers", name=name,
                                line=dict(width=2.4, color=colors[name]), marker=dict(size=5),
                            ))
                else:
                    fig.add_trace(go.Scatter(
                        x=weekly["week"], y=weekly["Overall Engagement"], mode="lines+markers",
                        name="Overall Engagement", line=dict(width=2.6, color="#3F72B5"),
                    ))
                _base_figure_layout(fig, x_title="Course week", y_title="Average interactions per learner", height=350)
                st.plotly_chart(fig, use_container_width=True, key=f"class_engagement_{module}_{presentation}_{quarter}")

        with col_cons:
            st.markdown("**Students active each week**")
            st.caption("Percentage of enrolled learners with at least one VLE interaction in each week.")
            if weekly.empty or "Students Active (%)" not in weekly.columns:
                render_empty_state("Consistency trend unavailable", "Raw VLE data are not available for this cohort.")
            else:
                fig = go.Figure(go.Bar(
                    x=weekly["week"], y=weekly["Students Active (%)"],
                    marker_color="#8FC5A3",
                    hovertemplate="Week %{x}<br>Students active: %{y:.1f}%<extra></extra>",
                ))
                _base_figure_layout(fig, x_title="Course week", y_title="Students active (%)", height=350)
                fig.update_yaxes(range=[0, 100])
                st.plotly_chart(fig, use_container_width=True, key=f"class_consistency_{module}_{presentation}_{quarter}")

        st.markdown("### Behavioural support demand")
        col_issue, col_first = st.columns([1.2, 1])
        with col_issue:
            if issues is None or issues.empty:
                render_empty_state("Cohort behavioural insights unavailable", "Recommendation details are needed to aggregate common learning opportunities.")
            else:
                top = issues.head(7).copy()
                fig = go.Figure(go.Bar(
                    x=top["Prevalence"], y=top["issue_label"], orientation="h",
                    marker_color="#E2A56F",
                    hovertemplate="%{y}<br>%{x:.1f}% of learners<extra></extra>",
                ))
                _base_figure_layout(fig, x_title="Learners with this opportunity (%)", y_title="", height=330)
                fig.update_layout(showlegend=False)
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True, key=f"cohort_issues_{module}_{presentation}_{quarter}")
                st.caption("A common issue may indicate a course-level teaching opportunity rather than an individual deficit.")
        with col_first:
            st.markdown("**Attention first**")
            st.caption("Top learners from the existing behavioural recommendation priority queue.")
            _queue_table(enriched_queue.sort_values(["Support Rank"], ascending=True) if not enriched_queue.empty else enriched_queue, compact=True)

    # ------------------------------------------------------------------
    # 2. SUPPORT QUEUE
    # ------------------------------------------------------------------
    with tabs[1]:
        st.subheader("Support Queue")
        st.caption(
            "The recommendation layer supplies the support status. Checkpoint engagement and assessment metrics add context; "
            "historical final outcomes are intentionally excluded."
        )

        if enriched_queue.empty:
            render_empty_state("Support queue unavailable", "Connect the recommendation exports to populate the instructor action queue.")
        else:
            legend_html = "<div class='tw-legend'>" + "".join(
                f"<span style='background:{meta['bg']};border-color:{meta['border']};color:{meta['text']}'>{level}</span>"
                for level, meta in SUPPORT_META.items()
            ) + "</div>"
            st.markdown(legend_html, unsafe_allow_html=True)

            f1, f2, f3 = st.columns([1.35, 1.1, 1.4])
            with f1:
                status_filter = st.multiselect(
                    "Support status",
                    list(SUPPORT_META),
                    default=list(SUPPORT_META),
                    key="instructor_status_filter",
                )
            with f2:
                student_search = st.text_input("Student ID", placeholder="Search ID", key="instructor_student_search")
            with f3:
                sort_by = st.selectbox(
                    "Sort",
                    ["Support priority", "Lowest active weeks", "Lowest engagement", "Most missed assessments"],
                    key="instructor_sort",
                )

            view = enriched_queue[enriched_queue["Support Status"].isin(status_filter)].copy()
            if student_search.strip():
                view = view[view["id_student"].astype(str).str.contains(student_search.strip(), regex=False)]

            if sort_by == "Support priority":
                cols = ["Support Rank"]
                ascending = [True]
                if "max_gap_severity" in view.columns:
                    view["_gap"] = pd.to_numeric(view["max_gap_severity"], errors="coerce").fillna(-1)
                    cols.append("_gap")
                    ascending.append(False)
                view = view.sort_values(cols, ascending=ascending)
            elif sort_by == "Lowest active weeks" and "Active Weeks %" in view.columns:
                view = view.sort_values("Active Weeks %", ascending=True)
            elif sort_by == "Lowest engagement" and "Engagement vs Class %" in view.columns:
                view = view.sort_values("Engagement vs Class %", ascending=True)
            elif sort_by == "Most missed assessments" and {"Assessments Submitted", "Assessments Due"}.issubset(view.columns):
                view["_missed"] = pd.to_numeric(view["Assessments Due"], errors="coerce").fillna(0) - pd.to_numeric(view["Assessments Submitted"], errors="coerce").fillna(0)
                view = view.sort_values(["_missed", "Support Rank"], ascending=[False, True])

            st.caption(f"Showing {len(view):,} learner records for the selected filters.")
            _queue_table(view)

            st.info(
                "Use this queue for prioritisation, then open Student Detail before contacting a learner. "
                "A support status is a decision-support signal, not an automatic academic decision."
            )

    # ------------------------------------------------------------------
    # 3. ASSESSMENTS
    # ------------------------------------------------------------------
    with tabs[2]:
        st.subheader("Assessments")
        st.caption(
            f"Assessment activity available by the {quarter} checkpoint only. Future assessments and submissions after Day {end_day} are not included."
        )

        due_count = assessment_stats.get("due_count", 0)
        submission_rate = assessment_stats.get("submission_rate")
        not_submitted = assessment_stats.get("not_submitted", 0)
        avg_score = assessment_stats.get("avg_score")

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            _metric_card("Assessments Due", str(due_count), f"By Week {end_week}")
        with a2:
            _metric_card("Submission Rate", f"{submission_rate:.0f}%" if submission_rate is not None else "—", "Across all due assessment opportunities")
        with a3:
            _metric_card("Not Submitted", f"{int(not_submitted):,}", "Student-assessment opportunities")
        with a4:
            _metric_card("Average Available Score", f"{avg_score:.1f}%" if avg_score is not None else "—", "Among submitted work by checkpoint")

        st.markdown("### Class score distribution")
        st.caption("Each box shows the class score distribution for one due assessment. Outliers remain visible for instructor context.")
        _assessment_boxplot(score_distribution, key=f"instructor_assessment_box_{module}_{presentation}_{quarter}")

        st.markdown("### Submission and timing overview")
        if assessment_metrics.empty:
            render_empty_state("No assessments due yet", "No assessment with a recorded due date falls before this checkpoint.")
        else:
            display = assessment_metrics.copy()
            display["Due week"] = (pd.to_numeric(display["date"], errors="coerce") / 7.0).apply(lambda x: int(math.ceil(x)) if pd.notna(x) else None)
            display["Weight (%)"] = pd.to_numeric(display.get("weight"), errors="coerce")
            display["Average score (%)"] = pd.to_numeric(display["Average score (%)"], errors="coerce").round(1)
            display["Submission rate (%)"] = pd.to_numeric(display["Submission rate (%)"], errors="coerce").round(1)
            display = display[[
                "Assessment", "Due week", "Weight (%)", "Submitted", "Submission rate (%)",
                "Not submitted", "Late", "Average score (%)",
            ]]
            st.dataframe(
                display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Submission rate (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                    "Average score (%)": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
            st.caption("Late = date_submitted later than the assessment due date. `is_banked` is not used as a lateness indicator.")

    # ------------------------------------------------------------------
    # 4. STUDENT DETAIL
    # ------------------------------------------------------------------
    with tabs[3]:
        st.subheader("Student Detail")
        st.caption(
            "Instructor view of the learner's Student dashboard: review the same behavioural evidence and progress context before choosing support."
        )

        queue_ids = set(enriched_queue["id_student"].astype(int).tolist()) if not enriched_queue.empty else set()
        cohort_ids = set(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).tolist()) if not cohort.empty else set()
        student_ids = sorted(queue_ids | cohort_ids)

        if not student_ids:
            render_empty_state("Student profiles unavailable", "No learner records are available for this module-presentation.")
            return

        student_id = st.selectbox(
            "Student ID",
            student_ids,
            format_func=lambda sid: f"Student {sid}",
            key="instructor_detail_student",
        )

        info = load_student_info()
        if not can_access_student(user, student_id, module, presentation, student_info=info):
            st.error("This learner is outside your assigned cohort.")
            st.stop()

        queue_row = {}
        if not enriched_queue.empty:
            match = enriched_queue[enriched_queue["id_student"].eq(int(student_id))]
            if not match.empty:
                queue_row = match.iloc[0].to_dict()
        if not queue_row and isinstance(summary, pd.DataFrame) and not summary.empty and "id_student" in summary.columns:
            sid = pd.to_numeric(summary["id_student"], errors="coerce")
            match = summary[sid.eq(int(student_id))]
            if not match.empty:
                queue_row = match.iloc[0].to_dict()

        level = _normalise_support(queue_row) if queue_row else "Needs Attention"
        pattern = student_learning_pattern(student_id, module, presentation, quarter)
        tiles = student_behaviour_tiles(student_id, module, presentation, quarter)
        recs = student_recommendations(student_id, module, presentation, quarter, limit=3)
        strengths, opportunities = student_strengths_opportunities(tiles)
        pred = prediction_for_student(student_id, module, presentation, quarter)
        opportunity = _first_existing(
            queue_row,
            ["Main opportunity", "main_opportunity", "primary_opportunity"],
            opportunities[0] if opportunities else "",
        )
        pattern_label = pattern.get("label", "Behavioural profile") if isinstance(pattern, dict) else "Behavioural profile"

        # --------------------------------------------------------------
        # Same front-page context used on the Student dashboard
        # --------------------------------------------------------------
        st.markdown("### Student & Course Context")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _detail_context_card("Student ID", student_id)
        with c2:
            _detail_context_card("Module", module)
        with c3:
            _detail_context_card("Presentation", presentation)
        with c4:
            _detail_context_card("Checkpoint", f"{quarter} · Weeks {start_week}–{end_week}")

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
            for col, (label, value) in zip(cols, demographic_items[start_idx:start_idx + 4]):
                with col:
                    _detail_context_card(label, value)

        _support_banner(student_id, level, pattern_label, str(opportunity))
        _render_priority_recommendation_block(recs, fallback_issue=str(opportunity))

        detail_tabs = st.tabs(["Student Overview", "Assessments", "Recommendations"])

        # ==============================================================
        # MY LEARNING
        # ==============================================================
        with detail_tabs[0]:
            st.markdown("### Behavioural Learning Indicators")
            st.caption(
                "The same student-facing behavioural signals are shown here so the instructor can understand why support is being suggested."
            )
            _grouped_behaviour_cards(tiles)

            st.markdown("### What the Learning Pattern Is Telling Us")
            s1, s2 = st.columns(2)
            with s1:
                st.markdown("**What is working well**")
                if strengths:
                    for item in strengths[:3]:
                        st.markdown(f"✓ {escape(str(item))}")
                else:
                    st.caption("No clear strength has surfaced yet at this checkpoint.")
            with s2:
                st.markdown("**Areas to support**")
                if opportunities:
                    for item in opportunities[:3]:
                        st.markdown(f"→ {escape(str(item))}")
                else:
                    st.caption("No meaningful behavioural opportunity has surfaced.")

            st.divider()
            st.markdown("### Explore Student Progress")
            progress_view = st.radio(
                "Progress view",
                ["Engagement", "Consistency", "Assessment"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"instructor_detail_progress_{student_id}_{quarter}",
            )

            student_assessment_details, student_assessment_summary = _student_assessment_detail(
                raw, student_id, assessment_metrics, score_distribution, end_week
            )

            if progress_view == "Engagement":
                _render_student_engagement_detail(raw, student_id, module, presentation, quarter, course_weeks)
            elif progress_view == "Consistency":
                _render_student_consistency_detail(
                    raw, student_id, module, presentation, start_week, end_week, quarter
                )
            else:
                a1, a2 = st.columns(2)
                with a1:
                    _render_student_assessment_progress(student_assessment_details, student_id, quarter)
                with a2:
                    st.markdown("#### Student Score Within Class Distribution")
                    st.caption("Class box plots use only assessment submissions available by this checkpoint; the diamond marks this student's score.")
                    _assessment_boxplot(
                        score_distribution,
                        student_id=student_id,
                        key=f"detail_learning_assessment_box_{student_id}_{quarter}",
                    )
                if student_assessment_summary.get("missing"):
                    st.warning(
                        "**Assessment not submitted at this checkpoint:** "
                        + ", ".join(student_assessment_summary["missing"])
                        + ". No personal score marker is shown for these assessments."
                    )

        # ==============================================================
        # ASSESSMENTS
        # ==============================================================
        with detail_tabs[1]:
            st.markdown("### Student Assessments")
            st.caption(
                f"Assessment information available by Week {end_week}. Later submissions and scores are intentionally excluded from this historical checkpoint view."
            )

            student_assessment_details, student_assessment_summary = _student_assessment_detail(
                raw, student_id, assessment_metrics, score_distribution, end_week
            )

            if student_assessment_details.empty:
                render_empty_state("Assessment information unavailable", "No assessment with a recorded due date is available by this checkpoint.")
            else:
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    _metric_card("Submitted", f"{student_assessment_summary['submitted']} / {student_assessment_summary['due']}", "Due by this checkpoint")
                with m2:
                    avg = student_assessment_summary.get("avg_score")
                    _metric_card("Average Score", f"{avg:.0f}%" if avg is not None else "—", "Available submitted assessments")
                with m3:
                    _metric_card("On Time", f"{student_assessment_summary['on_time']} / {student_assessment_summary['submitted']}", "Submitted on or before deadline")
                with m4:
                    _metric_card("Not Submitted", str(len(student_assessment_summary.get("missing", []))), "At this checkpoint")

                display = student_assessment_details.copy()
                display["Score %"] = pd.to_numeric(display["score"], errors="coerce")
                display["Weight %"] = pd.to_numeric(display.get("weight"), errors="coerce")
                display = display[["Assessment", "assessment_type", "Due Week", "Submitted Week", "Timing", "Score %", "Weight %"]]
                display = display.rename(columns={"assessment_type": "Type"})
                st.dataframe(display, hide_index=True, use_container_width=True)

                st.markdown("#### Submission Timing")
                timing = student_assessment_details.dropna(subset=["date_submitted"]).copy()
                if timing.empty:
                    st.caption("No submitted assessment is available for a timing chart at this checkpoint.")
                else:
                    timing["Days before deadline"] = timing["due_date"] - timing["date_submitted"]
                    fig = go.Figure(go.Bar(
                        x=timing["Assessment"],
                        y=timing["Days before deadline"],
                        text=timing["Timing"],
                        textposition="auto",
                        marker_color="#6E8FC7",
                    ))
                    fig.add_hline(y=0, line_dash="dash", line_color="#98A2B3", annotation_text="Deadline")
                    _base_figure_layout(fig, x_title="Assessment", y_title="Days before deadline", height=330)
                    st.plotly_chart(fig, use_container_width=True, key=f"detail_assessment_timing_{student_id}_{quarter}")

                st.markdown("#### Class Score Distribution by Assessment")
                st.caption("Each box shows the class score distribution available by this checkpoint. The diamond marks this student's score when submitted.")
                _assessment_boxplot(
                    score_distribution,
                    student_id=student_id,
                    key=f"detail_assessment_box_{student_id}_{quarter}",
                )

                if student_assessment_summary.get("missing"):
                    st.warning(
                        "**Assessment not submitted at this checkpoint:** "
                        + ", ".join(student_assessment_summary["missing"])
                        + ". The class distribution is still shown for context, but no personal score marker appears."
                    )

        # ==============================================================
        # RECOMMENDATIONS + TUTOR CHECK-IN
        # ==============================================================
        with detail_tabs[2]:
            st.markdown("### Personalised Recommendations")
            st.caption(
                "Recommendations are behavioural decision-support suggestions. Review the learner's context before deciding whether and how to contact them."
            )
            _recommendation_cards(recs, level)

            st.divider()
            st.markdown("### Tutor Check-in")
            st.caption(
                "Use this panel to record an illustrative human follow-up. OULAD contains no real intervention history or intervention outcomes."
            )

            suggested_actions = [r.get("action") for r in recs if r.get("action")]
            options = []
            for action_name in ["Tutor check-in"] + suggested_actions + ["Study planning support", "Assessment reminder"]:
                if action_name and action_name not in options:
                    options.append(action_name)

            action = st.selectbox(
                "Tutor action",
                options,
                index=0,
                key=f"intervention_action_{student_id}_{quarter}",
            )
            note = st.text_area(
                "Tutor note",
                placeholder="Optional context for the check-in",
                key=f"intervention_note_{student_id}_{quarter}",
            )
            if st.button(
                "Create Tutor Check-in",
                type="primary",
                key=f"create_intervention_{student_id}_{quarter}",
            ):
                create_intervention(
                    student_id=student_id,
                    learner=f"Student {student_id}",
                    module=module,
                    presentation=presentation,
                    quarter=quarter,
                    action=action,
                    note=note,
                    owner=user.get("display_name", "Instructor"),
                )
                st.success("Tutor check-in recorded for this demonstration session.")

            items = list_interventions(module=module, presentation=presentation)
            items = [
                item for item in items
                if str(item.get("learner", "")).endswith(str(student_id))
            ] if items else []
            if items:
                st.markdown("#### Tutor Check-in History")
                for item in items:
                    h1, h2, h3 = st.columns([5, 2, 2])
                    with h1:
                        st.markdown(
                            f"**{escape(str(item['action']))}**  \n"
                            f"{escape(str(item['created_at']))} · {escape(str(item.get('note') or 'No note'))}"
                        )
                    with h2:
                        st.write(item["status"])
                    with h3:
                        if item["status"] != "Completed" and st.button(
                            "Mark completed",
                            key=f"complete_{item['id']}",
                        ):
                            update_status(item["id"], "Completed")
                            st.rerun()
            else:
                st.caption("No tutor check-in has been recorded for this learner in this session.")

            with st.expander("Technical details", expanded=False):
                if pred and pred.get("probability") is not None:
                    st.write(f"Model probability: **{pred['probability']:.3f}**")
                    st.write(
                        f"Model: {pred.get('model_name') or 'Not supplied'} · "
                        f"Threshold: {pred.get('threshold') if pred.get('threshold') is not None else 'Not supplied'}"
                    )
                else:
                    st.write(
                        "Student-level prediction output is not connected yet. The support profile is currently driven by the behavioural recommendation layer."
                    )
                st.write("Historical final_result is deliberately excluded from this operational instructor view.")
                st.write("Use analytics as decision support and combine them with tutor judgement and learner context before acting.")

