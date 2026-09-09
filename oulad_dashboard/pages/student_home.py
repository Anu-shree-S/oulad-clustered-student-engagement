"""TrackWise Student Learning Companion.

Student-facing design principles:
- exactly three tabs: My Learning, Assessments, Recommendations;
- show the signed-in learner's real OULAD student ID and course/background context;
- use pedagogically grounded behavioural indicators rather than a synthetic health score;
- compare the learner with their own earlier behaviour and with the SAME module-presentation;
- respect course-specific Q1-Q4 boundaries from the EDA pipeline;
- never expose final_result or use it as an operational Student-page signal.
"""

from __future__ import annotations

from html import escape
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.permissions import can_access_module, can_access_student, require_role
from components.layout import (
    render_empty_state,
    render_metric_card,
    render_page_heading,
    render_status_banner,
    ribbon_start,
)
from services.data_service import load_dashboard_data, load_student_info

try:
    from config.paths import RAW_DATA_DIR
except Exception:
    RAW_DATA_DIR = None
from services.learning_service import (
    QUARTER_LABELS,
    analytics_status,
    load_behaviour_table,
    student_behaviour_tiles,
    student_recommendation_row,
    student_recommendations,
    student_strengths_opportunities,
)


# -----------------------------------------------------------------------------
# Student-facing copy
# -----------------------------------------------------------------------------

BEHAVIOUR_HELP = {
    "overall_engagement": (
        "Overall Engagement",
        "How actively you have used the online learning environment across the course so far.",
    ),
    "course_materials": (
        "Course Materials",
        "Your interaction with learning content such as pages, resources and course materials.",
    ),
    "assessment_engagement": (
        "Practice & Assessments",
        "Your interaction with assessment and practice-related learning activities.",
    ),
    "social_engagement": (
        "Learning With Others",
        "Your participation in collaborative or social learning activities such as forums and wikis.",
    ),
    "learning_balance": (
        "Learning Balance",
        "How evenly your activity is spread across different kinds of learning activity.",
    ),
    "study_consistency": (
        "Study Consistency",
        "The proportion of available course weeks in which you were active at least once.",
    ),
    "study_spacing": (
        "Study Spacing",
        "How well your study activity is spread over time rather than concentrated into short bursts.",
    ),
    "weekly_regularity": (
        "Weekly Regularity",
        "How evenly your engagement is distributed across the available course weeks.",
    ),
    "study_timing": (
        "Assessment Timing",
        "How early or late you tend to submit relative to the available assessment window.",
    ),
    "assessment_participation": (
        "Assessments Submitted",
        "The number of assessments you have submitted using information available by this checkpoint.",
    ),
    "deadline_adherence": (
        "Deadline Adherence",
        "The number of submitted assessments that were after their scheduled deadline by this checkpoint.",
    ),
}

STATUS_EXPLANATION = {
    "Strong": "This is currently one of your stronger learning habits compared with the reference pattern.",
    "Steady": "This learning habit is broadly steady for your current course context.",
    "Building": "This habit is developing and could benefit from a little more consistency.",
    "Opportunity": "This is the clearest area where a small change may strengthen your learning routine.",
    "Observed": "There is enough information to describe this behaviour, but not enough for a reliable relative status.",
}

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Exact engagement-dimension mapping used by the EDA feature pipeline.
CONTENT_TYPES = {
    "subpage", "homepage", "oucontent", "resource", "url", "page",
    "folder", "glossary", "htmlactivity", "dualpane", "repeatactivity",
}
ASSESSMENT_TYPES = {"quiz", "externalquiz", "questionnaire"}
SOCIAL_TYPES = {
    "forumng", "ouwiki", "oucollaborate", "ouelluminate",
    "dataplus", "sharedsubpage",
}

# Student-facing wording for the three operational support levels.
# The underlying recommendation status is preserved; only the visible wording is softened.
STUDENT_SUPPORT_COPY = {
    "steady": (
        "Going well",
        "Your current learning pattern is broadly steady. Keep the habits that are working for you.",
        "success",
    ),
    "attention": (
        "Build some momentum",
        "A few learning habits could benefit from a little more attention at this checkpoint.",
        "primary",
    ),
    "support": (
        "Some extra support could help",
        "A few learning behaviours would benefit from more structured support. Start with the recommendations below.",
        "warning",
    ),
}


# Student-only pastel status styles. Keeping these local prevents changes to
# shared Instructor/Admin dashboard styling.
STUDENT_STATUS_STYLES = """
<style>
.tw-habit {
    border-radius: 16px !important;
    padding: 18px 20px !important;
    min-height: 158px;
    height: 100%;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.tw-habit:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
}
.tw-habit small {
    display: block;
    font-size: .72rem;
    font-weight: 800;
    letter-spacing: .045em;
    text-transform: uppercase;
    color: #53657d;
}
.tw-habit strong {
    display: block;
    margin: .42rem 0 .36rem;
    font-size: 1.05rem;
    font-weight: 750;
    color: #102542;
}

/* Engagement cards use a qualitative relative indicator rather than a score.
   Keep that descriptor secondary and make the behavioural status the focus. */
.tw-habit .relative-indicator {
    display: block;
    margin: .44rem 0 .16rem;
    font-size: .80rem;
    font-weight: 500;
    color: #667085;
}
.tw-habit b {
    display: block;
    font-size: .9rem;
    font-weight: 800;
}
.tw-habit b.primary-status {
    font-size: 1.12rem;
    line-height: 1.2;
    font-weight: 800;
    margin: .10rem 0 .18rem;
}
.tw-habit p {
    margin: .55rem 0 0 !important;
    font-size: .82rem !important;
    line-height: 1.45 !important;
    color: #4f627b !important;
}

/* Strong / Steady */
.tw-habit-success {
    background: #edf8f0 !important;
    border: 1px solid #c8e7d0 !important;
}
.tw-habit-success b { color: #287a49 !important; }

/* Building */
.tw-habit-warning {
    background: #fff4e5 !important;
    border: 1px solid #f2d4a8 !important;
}
.tw-habit-warning b { color: #a96312 !important; }

/* Opportunity */
.tw-habit-danger {
    background: #fdecec !important;
    border: 1px solid #efbcbc !important;
}
.tw-habit-danger b { color: #b44848 !important; }

/* Observed / descriptive only */
.tw-habit-neutral {
    background: #f3f6fa !important;
    border: 1px solid #dbe3ed !important;
}
.tw-habit-neutral b { color: #53657d !important; }

/* Fully-filled current support status */
.tw-learning-support {
    border-radius: 18px;
    padding: 22px 26px;
    margin: .8rem 0 1.2rem;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}
.tw-learning-support .eyebrow {
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .075em;
    text-transform: uppercase;
    color: #53657d;
}
.tw-learning-support h2 {
    margin: .32rem 0 .38rem;
    font-size: 1.58rem;
    line-height: 1.2;
    color: #102542;
}
.tw-learning-support p {
    margin: 0;
    font-size: 1rem;
    line-height: 1.5;
    color: #53657d;
}
.tw-support-success {
    background: #edf8f0;
    border: 1px solid #c8e7d0;
    border-left: 6px solid #69ad79;
}
.tw-support-primary {
    background: #eef4ff;
    border: 1px solid #cad9f4;
    border-left: 6px solid #6f94d0;
}
.tw-support-warning {
    background: #fff4e5;
    border: 1px solid #f2d4a8;
    border-left: 6px solid #d59a43;
}
.tw-support-danger {
    background: #fdecec;
    border: 1px solid #efbcbc;
    border-left: 6px solid #d56666;
}

/* Prominent plain-language priority recommendation */
.tw-priority-rec {
    background: #eef4ff;
    border: 1px solid #cad9f4;
    border-left: 6px solid #6f94d0;
    border-radius: 16px;
    padding: 18px 20px;
    margin: .9rem 0 1.25rem;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.tw-priority-rec .eyebrow {
    color: #53657d; font-size: .72rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: .055em;
}
.tw-priority-rec .gap {
    color: #667085; font-size: .80rem; margin: .35rem 0 .45rem;
}
.tw-priority-rec .recommendation {
    color: #102542; font-size: 1.08rem; font-weight: 750; line-height: 1.5;
}
.tw-priority-rec .reason {
    color: #53657d; font-size: .84rem; line-height: 1.45; margin-top: .55rem;
}
</style>
"""


def _inject_student_status_styles():
    """Apply Student-only pastel status styling."""
    st.markdown(STUDENT_STATUS_STYLES, unsafe_allow_html=True)


def _behaviour_tone(status: str) -> str:
    """Map behavioural status to a pastel card tone."""
    value = str(status or "").strip().lower()
    if value in {"strong", "steady"}:
        return "success"
    if value == "building":
        return "warning"
    if value == "opportunity":
        return "danger"
    return "neutral"


def _render_learning_support_status(title: str, message: str, tone: str):
    """Render the current learning-support status as a fully filled block."""
    safe_tone = str(tone or "primary").strip().lower()
    if safe_tone not in {"success", "primary", "warning", "danger"}:
        safe_tone = "primary"
    st.markdown(
        f"""
        <div class="tw-learning-support tw-support-{safe_tone}">
          <div class="eyebrow">Current learning-support status</div>
          <h2>{escape(str(title))}</h2>
          <p>{escape(str(message))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Data helpers
# -----------------------------------------------------------------------------


def _safe_number(value, default=None):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return default
    return float(parsed)


def _load_raw_tables():
    """Normalise the dashboard data service response to the four tables used here."""
    loaded = load_dashboard_data()
    if isinstance(loaded, dict):
        def pick(*names):
            for name in names:
                value = loaded.get(name)
                if value is not None:
                    return value
            return None
        return (
            pick("studentInfo", "student_info"),
            pick("studentVle", "student_vle"),
            pick("studentAssessment", "student_assessment"),
            pick("assessments"),
        )
    if isinstance(loaded, (list, tuple)) and len(loaded) >= 4:
        return loaded[0], loaded[1], loaded[2], loaded[3]
    raise ValueError("load_dashboard_data() did not return the expected OULAD tables.")


@st.cache_data(show_spinner=False)
def _combined_behaviour_table(quarter: str) -> pd.DataFrame:
    """Load train + test behavioural rows so Student views are not limited to one split."""
    frames = []
    for cohort in ("train", "test"):
        try:
            frame = load_behaviour_table(quarter, cohort=cohort)
        except TypeError:
            # Compatibility with an older service signature that only exposes test.
            if cohort == "test":
                frame = load_behaviour_table(quarter)
            else:
                frame = pd.DataFrame()
        except Exception:
            frame = pd.DataFrame()
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True, sort=False)
    keys = [c for c in ["id_student", "code_module", "code_presentation"] if c in combined.columns]
    if keys:
        combined = combined.drop_duplicates(subset=keys, keep="last")
    return combined


def _filter_enrolment(df: pd.DataFrame, student_id: int, module: str, presentation: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    needed = {"id_student", "code_module", "code_presentation"}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    sid = pd.to_numeric(df["id_student"], errors="coerce")
    return df[
        sid.eq(int(student_id))
        & df["code_module"].astype(str).eq(str(module))
        & df["code_presentation"].astype(str).eq(str(presentation))
    ].copy()


def _behaviour_row(student_id: int, module: str, presentation: str, quarter: str) -> dict:
    frame = _filter_enrolment(_combined_behaviour_table(quarter), student_id, module, presentation)
    return {} if frame.empty else frame.iloc[0].to_dict()


def _course_cutoffs(module: str, presentation: str, quarter: str) -> dict:
    """Read the EDA-generated course-specific quarter boundaries from behavioural exports.

    Fallback follows the exact EDA rule: 38 weeks -> 10/19/29/38,
    34 weeks -> 9/17/26/34, otherwise proportional quarters.
    """
    table = _combined_behaviour_table(quarter)
    if not table.empty and {"code_module", "code_presentation"}.issubset(table.columns):
        course = table[
            table["code_module"].astype(str).eq(str(module))
            & table["code_presentation"].astype(str).eq(str(presentation))
        ]
        if not course.empty:
            row = course.iloc[0]
            values = {}
            for name in ["course_weeks", "q1_end", "q2_end", "q3_end", "q4_end"]:
                if name in row.index:
                    val = _safe_number(row.get(name))
                    if val is not None:
                        values[name] = int(round(val))
            if all(k in values for k in ["q1_end", "q2_end", "q3_end", "q4_end"]):
                values.setdefault("course_weeks", values["q4_end"])
                return values

    # Raw-data fallback: estimate presentation length from observed positive VLE dates.
    # This is used only when the exported EDA windows are unavailable.
    _, vle, _, _ = _load_raw_tables()
    course_weeks = None
    if isinstance(vle, pd.DataFrame) and not vle.empty:
        course_vle = vle[
            vle["code_module"].astype(str).eq(str(module))
            & vle["code_presentation"].astype(str).eq(str(presentation))
        ].copy()
        if not course_vle.empty:
            dates = pd.to_numeric(course_vle["date"], errors="coerce")
            dates = dates[dates >= 0]
            if not dates.empty:
                course_weeks = max(1, int(math.ceil((float(dates.max()) + 1) / 7)))

    course_weeks = int(course_weeks or 38)
    if course_weeks == 38:
        ends = (10, 19, 29, 38)
    elif course_weeks == 34:
        ends = (9, 17, 26, 34)
    else:
        ends = (
            max(1, int(math.ceil(course_weeks * 0.25))),
            min(course_weeks, int(math.ceil(course_weeks * 0.50))),
            min(course_weeks, int(math.ceil(course_weeks * 0.75))),
            course_weeks,
        )
    return {
        "course_weeks": course_weeks,
        "q1_end": ends[0],
        "q2_end": ends[1],
        "q3_end": ends[2],
        "q4_end": ends[3],
    }


def _quarter_end_week(cutoffs: dict, quarter: str) -> int:
    return int(cutoffs.get(f"{quarter.lower()}_end", cutoffs.get("course_weeks", 38)))


def _profile_row(info: pd.DataFrame, student_id: int, module: str, presentation: str) -> dict:
    frame = _filter_enrolment(info, student_id, module, presentation)
    return {} if frame.empty else frame.iloc[0].to_dict()


def _context_block(label: str, value: str):
    """High-contrast context block for Student ID / course / presentation."""
    st.markdown(
        f"""
        <div style='padding:.45rem .15rem;'>
          <div style='font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--tw-muted);'>{escape(str(label))}</div>
          <div style='font-size:1.12rem;font-weight:700;color:var(--tw-heading);margin-top:.12rem'>{escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _student_support_view(summary: dict) -> tuple[str, str, str]:
    """Map operational recommendation status to supportive Student-facing wording."""
    raw = str(summary.get("support_status") or "").strip().lower()
    intervention = str(summary.get("intervention_level") or "").strip().lower()

    if any(token in raw for token in ["on track", "going well", "steady"]):
        level = "steady"
    elif any(token in raw for token in ["priority", "urgent", "support recommended", "extra support"]):
        level = "support"
    elif any(token in raw for token in ["attention", "momentum", "building"]):
        level = "attention"
    elif intervention in {"instructor follow-up", "targeted support"}:
        level = "support"
    elif intervention == "self-guided support":
        level = "attention"
    else:
        level = "steady"

    return STUDENT_SUPPORT_COPY[level]


def _load_vle_metadata() -> pd.DataFrame:
    """Load vle.csv metadata used to classify VLE sites as content/assessment/social.

    Prefer the central dashboard data service. Fall back to RAW_DATA_DIR so this
    page still works with the project path configuration used by the dashboard.
    """
    try:
        loaded = load_dashboard_data()
    except Exception:
        loaded = None

    if isinstance(loaded, dict):
        for key in ("vle", "VLE", "vle_metadata"):
            value = loaded.get(key)
            if isinstance(value, pd.DataFrame) and not value.empty:
                return value.copy()
    elif isinstance(loaded, (list, tuple)):
        # Common OULAD loader order when all seven raw tables are returned:
        # studentInfo, studentVle, studentAssessment, assessments,
        # studentRegistration, courses, vle.
        for value in loaded[4:]:
            if isinstance(value, pd.DataFrame) and {"id_site", "activity_type"}.issubset(value.columns):
                return value.copy()

    candidates = []
    if RAW_DATA_DIR is not None:
        candidates.append(Path(RAW_DATA_DIR) / "vle.csv")
    # Safe project-relative fallback; does not depend on the current working directory.
    candidates.append(Path(__file__).resolve().parents[2] / "data" / "raw" / "vle.csv")

    for path in candidates:
        try:
            if path.exists():
                frame = pd.read_csv(path)
                if {"id_site", "activity_type"}.issubset(frame.columns):
                    return frame
        except Exception:
            continue
    return pd.DataFrame()


def _engagement_dimension(activity_type) -> str:
    if pd.isna(activity_type):
        return "other"
    value = str(activity_type).strip().lower()
    if value in CONTENT_TYPES:
        return "content"
    if value in ASSESSMENT_TYPES:
        return "assessment"
    if value in SOCIAL_TYPES:
        return "social"
    return "other"


def _quarter_week_bounds(cutoffs: dict, quarter: str) -> tuple[int, int]:
    """Inclusive start/end course week for the selected quarter."""
    idx = QUARTERS.index(quarter)
    end_week = _quarter_end_week(cutoffs, quarter)
    if idx == 0:
        return 1, end_week
    previous = QUARTERS[idx - 1]
    return _quarter_end_week(cutoffs, previous) + 1, end_week


def _engagement_current_quarter(
    student_id: int,
    module: str,
    presentation: str,
    quarter: str,
    cutoffs: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, float | None, tuple[int, int], bool]:
    """Build Student weekly engagement and an actual same-class mean.

    Returns
    -------
    weekly:
        One row per course week in the selected quarter with the learner's
        Course Materials, Practice & Assessments, Learning With Others and
        Overall Engagement interaction counts.
    comparison:
        Selected-quarter totals for the learner versus the arithmetic class
        mean.  The class mean is calculated exactly as requested:
        sum of interactions across ALL enrolled students / number of enrolled
        students in the module-presentation. Students with zero activity are
        therefore included in the denominator.
    previous_overall_weekly_average:
        For Q2-Q4 only, the learner's average weekly Overall Engagement during
        the immediately preceding quarter. This is intentionally a single
        overall reference, not four previous-quarter series.
    bounds:
        Inclusive current-quarter week range.
    dimensions_available:
        Whether vle.csv activity_type metadata was available.
    """
    info, student_vle, _, _ = _load_raw_tables()
    start_week, end_week = _quarter_week_bounds(cutoffs, quarter)

    if not isinstance(student_vle, pd.DataFrame) or student_vle.empty:
        return pd.DataFrame(), pd.DataFrame(), None, (start_week, end_week), False

    course = student_vle[
        student_vle["code_module"].astype(str).eq(str(module))
        & student_vle["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if course.empty:
        return pd.DataFrame(), pd.DataFrame(), None, (start_week, end_week), False

    course["id_student"] = pd.to_numeric(course["id_student"], errors="coerce")
    course["date"] = pd.to_numeric(course["date"], errors="coerce")
    course["sum_click"] = pd.to_numeric(course["sum_click"], errors="coerce").fillna(0).clip(lower=0)
    course = course[course["date"].ge(0)].copy()
    course["week"] = (course["date"] // 7 + 1).astype(int)

    vle_meta = _load_vle_metadata()
    dimensions_available = isinstance(vle_meta, pd.DataFrame) and not vle_meta.empty and {"id_site", "activity_type"}.issubset(vle_meta.columns)
    if dimensions_available:
        lookup = vle_meta[["id_site", "activity_type"]].drop_duplicates("id_site")
        course = course.merge(lookup, on="id_site", how="left")
        course["engagement_dim"] = course["activity_type"].apply(_engagement_dimension)
    else:
        course["engagement_dim"] = "other"

    # Class size comes from ALL enrolled students, not only students with VLE rows.
    if isinstance(info, pd.DataFrame) and not info.empty:
        enrolled = info[
            info["code_module"].astype(str).eq(str(module))
            & info["code_presentation"].astype(str).eq(str(presentation))
        ]
        cohort_ids = pd.to_numeric(enrolled["id_student"], errors="coerce").dropna().astype(int).unique()
        class_size = int(len(cohort_ids))
    else:
        cohort_ids = pd.to_numeric(course["id_student"], errors="coerce").dropna().astype(int).unique()
        class_size = int(len(cohort_ids))

    class_size = max(class_size, 1)
    current = course[course["week"].between(start_week, end_week)].copy()
    mine = current[current["id_student"].eq(int(student_id))].copy()
    weeks = pd.Index(range(start_week, end_week + 1), name="week")

    label_to_dim = {
        "Course Materials": "content",
        "Practice & Assessments": "assessment",
        "Learning With Others": "social",
    }

    weekly = pd.DataFrame({"week": weeks})
    for label, dim in label_to_dim.items():
        if dimensions_available:
            values = (
                mine[mine["engagement_dim"].eq(dim)]
                .groupby("week")["sum_click"].sum()
                .reindex(weeks, fill_value=0.0)
            )
            weekly[label] = values.to_numpy(dtype=float)
        else:
            weekly[label] = pd.NA

    overall = mine.groupby("week")["sum_click"].sum().reindex(weeks, fill_value=0.0)
    weekly["Overall Engagement"] = overall.to_numpy(dtype=float)

    # Current-quarter actual totals: ME vs arithmetic class average.
    comparison_rows = []
    for label, dim in label_to_dim.items():
        if dimensions_available:
            me_total = float(mine.loc[mine["engagement_dim"].eq(dim), "sum_click"].sum())
            class_total = float(current.loc[current["engagement_dim"].eq(dim), "sum_click"].sum())
            comparison_rows.append({
                "Metric": label,
                "ME": me_total,
                "Class Average": class_total / class_size,
            })

    comparison_rows.append({
        "Metric": "Overall Engagement",
        "ME": float(mine["sum_click"].sum()),
        "Class Average": float(current["sum_click"].sum()) / class_size,
    })
    comparison = pd.DataFrame(comparison_rows)

    previous_average = None
    quarter_index = QUARTERS.index(quarter)
    if quarter_index > 0:
        previous_quarter = QUARTERS[quarter_index - 1]
        prev_start, prev_end = _quarter_week_bounds(cutoffs, previous_quarter)
        previous_mine = course[
            course["id_student"].eq(int(student_id))
            & course["week"].between(prev_start, prev_end)
        ]
        previous_weeks = max(1, prev_end - prev_start + 1)
        previous_average = float(previous_mine["sum_click"].sum()) / previous_weeks

    return weekly, comparison, previous_average, (start_week, end_week), dimensions_available


def _weekly_engagement(student_id: int, module: str, presentation: str, end_week: int) -> tuple[pd.DataFrame, dict]:
    """Weekly Student activity and TRUE class average including zero-activity learners."""
    info, vle, _, _ = _load_raw_tables()
    if vle is None or vle.empty:
        return pd.DataFrame(), {}

    course = vle[
        vle["code_module"].astype(str).eq(str(module))
        & vle["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if course.empty:
        return pd.DataFrame(), {}

    course["date"] = pd.to_numeric(course["date"], errors="coerce")
    course["sum_click"] = pd.to_numeric(course["sum_click"], errors="coerce").fillna(0)
    course = course[course["date"].ge(0)].copy()
    course["week"] = (course["date"] // 7 + 1).astype(int)
    course = course[course["week"].between(1, int(end_week))]

    weeks = pd.Index(range(1, int(end_week) + 1), name="week")
    student_weekly = (
        course[course["id_student"].eq(student_id)]
        .groupby("week")["sum_click"].sum()
        .reindex(weeks, fill_value=0.0)
    )

    if isinstance(info, pd.DataFrame) and not info.empty:
        cohort = info[
            info["code_module"].astype(str).eq(str(module))
            & info["code_presentation"].astype(str).eq(str(presentation))
        ]
        cohort_ids = pd.Index(pd.to_numeric(cohort["id_student"], errors="coerce").dropna().astype(int).unique())
    else:
        cohort_ids = pd.Index(pd.to_numeric(course["id_student"], errors="coerce").dropna().astype(int).unique())

    grouped = course.groupby(["id_student", "week"])["sum_click"].sum()
    full_index = pd.MultiIndex.from_product([cohort_ids, weeks], names=["id_student", "week"])
    full = grouped.reindex(full_index, fill_value=0.0)
    course_weekly_avg = full.groupby("week").mean()

    chart = pd.DataFrame({
        "week": weeks,
        "My activity": student_weekly.values,
        "Class average": course_weekly_avg.reindex(weeks, fill_value=0.0).values,
    })

    per_student_total = course.groupby("id_student")["sum_click"].sum().reindex(cohort_ids, fill_value=0.0)
    totals = {
        "student": float(student_weekly.sum()),
        "course_average": float(per_student_total.mean()) if len(per_student_total) else 0.0,
    }
    return chart, totals


def _weekly_consistency_data(
    student_id: int,
    module: str,
    presentation: str,
    quarter: str,
    cutoffs: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build an intuitive within-quarter study-consistency view.

    Consistency follows the EDA definition behind ``active_weeks_ratio``:
    a week is active when the learner records at least one VLE interaction.

    Returns
    -------
    progress:
        One row per week in the selected quarter with:
        - whether the learner was active that week (0/100 for display), and
        - the cumulative percentage of available weeks active so far.
    comparison:
        Week-level active-rate data retained for optional diagnostics. The
        student-facing comparison chart uses the quarter-level summary instead.
    summary:
        Current-quarter active-week counts and the class-average active-week
        percentage across the same quarter.
    """
    info, vle, _, _ = _load_raw_tables()
    start_week, end_week = _quarter_week_bounds(cutoffs, quarter)
    weeks = pd.Index(range(start_week, end_week + 1), name="week")

    if not isinstance(vle, pd.DataFrame) or vle.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    course = vle[
        vle["code_module"].astype(str).eq(str(module))
        & vle["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if course.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    course["id_student"] = pd.to_numeric(course["id_student"], errors="coerce")
    course["date"] = pd.to_numeric(course["date"], errors="coerce")
    course["sum_click"] = pd.to_numeric(course["sum_click"], errors="coerce").fillna(0).clip(lower=0)
    course = course[course["date"].ge(0)].copy()
    course["week"] = (course["date"] // 7 + 1).astype(int)
    current = course[course["week"].between(start_week, end_week)].copy()

    # Use every learner enrolled in this module-presentation as the class
    # denominator so students with no VLE activity remain zero-activity rows.
    if isinstance(info, pd.DataFrame) and not info.empty:
        enrolled = info[
            info["code_module"].astype(str).eq(str(module))
            & info["code_presentation"].astype(str).eq(str(presentation))
        ]
        cohort_ids = pd.Index(
            pd.to_numeric(enrolled["id_student"], errors="coerce")
            .dropna().astype(int).unique(),
            name="id_student",
        )
    else:
        cohort_ids = pd.Index(
            pd.to_numeric(course["id_student"], errors="coerce")
            .dropna().astype(int).unique(),
            name="id_student",
        )

    if len(cohort_ids) == 0:
        return pd.DataFrame(), pd.DataFrame(), {}

    grouped = current.groupby(["id_student", "week"])["sum_click"].sum()
    full_index = pd.MultiIndex.from_product(
        [cohort_ids, weeks], names=["id_student", "week"]
    )
    full = grouped.reindex(full_index, fill_value=0.0)
    active = full.gt(0).astype(float)

    # Student's actual active/inactive status for every week in the quarter.
    try:
        student_active = active.xs(int(student_id), level="id_student").reindex(weeks, fill_value=0.0)
    except KeyError:
        student_active = pd.Series(0.0, index=weeks)

    denominators = pd.Series(range(1, len(weeks) + 1), index=weeks, dtype=float)
    cumulative_pct = student_active.cumsum().div(denominators).mul(100.0)

    progress = pd.DataFrame({
        "week": weeks,
        "Active this week %": student_active.to_numpy() * 100.0,
        "Cumulative active weeks %": cumulative_pct.to_numpy(),
    })

    # True class average for each week = active enrolled learners / all enrolled learners.
    class_weekly_pct = active.groupby(level="week").mean().mul(100.0).reindex(weeks, fill_value=0.0)
    comparison = pd.DataFrame({
        "week": weeks,
        "ME": student_active.to_numpy() * 100.0,
        "Class Average": class_weekly_pct.to_numpy(),
    })

    # Quarter-level summary, useful for the plain-language note below the charts.
    class_per_student_ratio = active.groupby(level="id_student").mean().mul(100.0)
    summary = {
        "active_weeks": int(student_active.sum()),
        "quarter_weeks": int(len(weeks)),
        "student_pct": float(student_active.mean() * 100.0) if len(weeks) else 0.0,
        "class_pct": float(class_per_student_ratio.mean()) if not class_per_student_ratio.empty else 0.0,
        "inactive_weeks": [int(w) for w, v in student_active.items() if v == 0],
        "start_week": int(start_week),
        "end_week": int(end_week),
    }
    return progress, comparison, summary


def _assessment_data(student_id: int, module: str, presentation: str, end_week: int):
    """Assessment details available at the selected checkpoint plus same-course averages."""
    _, _, student_assessment, assessments = _load_raw_tables()
    if student_assessment is None or assessments is None or assessments.empty:
        return pd.DataFrame(), pd.DataFrame(), None

    ass = assessments[
        assessments["code_module"].astype(str).eq(str(module))
        & assessments["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if ass.empty:
        return pd.DataFrame(), pd.DataFrame(), None

    ass["date"] = pd.to_numeric(ass["date"], errors="coerce")
    ass["weight"] = pd.to_numeric(ass.get("weight"), errors="coerce")
    end_day = int(end_week) * 7

    # Assessments whose due date is available by this checkpoint.
    due = ass[ass["date"].notna() & ass["date"].le(end_day)].copy().sort_values("date")
    future = ass[ass["date"].notna() & ass["date"].gt(end_day)].sort_values("date")
    next_assessment = None if future.empty else future.iloc[0].to_dict()

    sa = student_assessment.copy()
    sa["date_submitted"] = pd.to_numeric(sa.get("date_submitted"), errors="coerce")
    sa["score"] = pd.to_numeric(sa.get("score"), errors="coerce")

    # At a historical checkpoint, do not reveal submissions/scores made after it.
    sa_known = sa[sa["date_submitted"].notna() & sa["date_submitted"].le(end_day)].copy()
    mine = due.merge(sa_known[sa_known["id_student"].eq(student_id)], on="id_assessment", how="left", suffixes=("", "_student"))

    if mine.empty:
        details = pd.DataFrame()
    else:
        mine["days_before_deadline"] = mine["date"] - mine["date_submitted"]

        def timing_text(row):
            if pd.isna(row.get("date_submitted")):
                return "Not submitted by checkpoint"
            delta = row.get("days_before_deadline")
            if pd.isna(delta):
                return "—"
            delta = int(round(delta))
            if delta > 0:
                return f"{delta} day{'s' if delta != 1 else ''} early"
            if delta == 0:
                return "On deadline"
            late = abs(delta)
            return f"{late} day{'s' if late != 1 else ''} late"

        mine["Timing"] = mine.apply(timing_text, axis=1)
        mine["Assessment"] = [f"{str(t).upper()} {i + 1}" for i, t in enumerate(mine.get("assessment_type", pd.Series("Task", index=mine.index)).astype(str))]
        mine["Due week"] = (mine["date"] / 7).apply(lambda x: int(math.ceil(x)) if pd.notna(x) else None)
        mine["Submitted week"] = (mine["date_submitted"] / 7).apply(lambda x: int(math.ceil(x)) if pd.notna(x) else None)
        details = mine[[
            "id_assessment", "Assessment", "assessment_type", "Due week", "Submitted week",
            "Timing", "score", "weight", "date", "date_submitted", "days_before_deadline"
        ]].copy()

    # Same module-presentation average for the SAME assessments and same historical cutoff.
    comparison = pd.DataFrame()
    if not due.empty:
        cohort_scores = sa_known[sa_known["id_assessment"].isin(due["id_assessment"])].copy()
        averages = cohort_scores.groupby("id_assessment")["score"].mean().rename("Class average")
        comparison = due[["id_assessment", "assessment_type", "date"]].merge(averages, on="id_assessment", how="left")
        if not details.empty:
            comparison = comparison.merge(details[["id_assessment", "score", "Assessment"]], on="id_assessment", how="left")
            comparison = comparison.rename(columns={"score": "My score"})
        else:
            comparison["My score"] = pd.NA
            comparison["Assessment"] = [f"{str(t).upper()} {i + 1}" for i, t in enumerate(comparison["assessment_type"].astype(str))]

    return details, comparison, next_assessment


def _assessment_boxplot_data(
    student_id: int,
    module: str,
    presentation: str,
    end_week: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build checkpoint-safe class score distributions for each due assessment.

    Returns
    -------
    distribution:
        One row per submitted class score available by the checkpoint, with a
        human-readable assessment label for box-plot grouping.
    student_scores:
        One row per due assessment with the signed-in learner's score when the
        learner had submitted by the checkpoint; otherwise score is missing.

    Scores/submissions recorded after the selected checkpoint are intentionally
    excluded so the historical Student view does not leak future information.
    """
    _, _, student_assessment, assessments = _load_raw_tables()
    if (
        not isinstance(student_assessment, pd.DataFrame)
        or student_assessment.empty
        or not isinstance(assessments, pd.DataFrame)
        or assessments.empty
    ):
        return pd.DataFrame(), pd.DataFrame()

    ass = assessments[
        assessments["code_module"].astype(str).eq(str(module))
        & assessments["code_presentation"].astype(str).eq(str(presentation))
    ].copy()
    if ass.empty:
        return pd.DataFrame(), pd.DataFrame()

    ass["date"] = pd.to_numeric(ass.get("date"), errors="coerce")
    end_day = int(end_week) * 7
    due = ass[ass["date"].notna() & ass["date"].le(end_day)].copy().sort_values("date")
    if due.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Match the assessment naming/order already used in the Student assessment table.
    due["Assessment"] = [
        f"{str(t).upper()} {i + 1}"
        for i, t in enumerate(
            due.get("assessment_type", pd.Series("Task", index=due.index)).astype(str)
        )
    ]

    sa = student_assessment.copy()
    sa["id_student"] = pd.to_numeric(sa.get("id_student"), errors="coerce")
    sa["date_submitted"] = pd.to_numeric(sa.get("date_submitted"), errors="coerce")
    sa["score"] = pd.to_numeric(sa.get("score"), errors="coerce")

    # Only submissions that were actually known by this checkpoint.
    sa_known = sa[
        sa["date_submitted"].notna()
        & sa["date_submitted"].le(end_day)
        & sa["id_assessment"].isin(due["id_assessment"])
    ].copy()

    distribution = sa_known.merge(
        due[["id_assessment", "Assessment"]],
        on="id_assessment",
        how="inner",
    )[["id_assessment", "Assessment", "id_student", "score"]].copy()
    distribution = distribution.dropna(subset=["score"])

    mine = sa_known[sa_known["id_student"].eq(int(student_id))][
        ["id_assessment", "score", "date_submitted"]
    ].copy()
    student_scores = due[["id_assessment", "Assessment"]].merge(
        mine,
        on="id_assessment",
        how="left",
    )

    return distribution, student_scores


# -----------------------------------------------------------------------------
# Behaviour cards and interpretation
# -----------------------------------------------------------------------------


def _tile_display_value(tile: dict) -> str:
    key = tile.get("key")
    value = _safe_number(tile.get("value"))
    if key in {"study_consistency", "study_spacing", "learning_balance"} and value is not None:
        return f"{100 * value:.0f}%"
    if key == "deadline_adherence" and value is not None:
        late = int(round(value))
        return f"{late} late"
    if key == "study_timing":
        return "Timing pattern"
    # Normalised engagement shares are technically useful but not an intuitive Student score.
    if key in {"overall_engagement", "course_materials", "assessment_engagement", "social_engagement"}:
        return "Relative indicator"
    return str(tile.get("value_text") or "Observed")


def _supplemental_tiles(student_id: int, module: str, presentation: str, quarter: str, existing_keys: set[str]) -> list[dict]:
    row = _behaviour_row(student_id, module, presentation, quarter)
    if not row:
        return []
    extra = []

    submissions_col = f"n_submissions_{quarter}"
    if "assessment_participation" not in existing_keys and submissions_col in row:
        value = _safe_number(row.get(submissions_col))
        if value is not None:
            extra.append({
                "key": "assessment_participation",
                "label": "Assessments Submitted",
                "status": "Observed",
                "value": value,
                "value_text": str(int(round(value))),
            })
    return extra


def _group_tiles(tiles: list[dict]) -> dict[str, list[dict]]:
    groups = {"Engagement": [], "Consistency": [], "Assessment behaviour": []}
    key_to_group = {
        "overall_engagement": "Engagement",
        "course_materials": "Engagement",
        "assessment_engagement": "Engagement",
        "social_engagement": "Engagement",
        "study_consistency": "Consistency",
        "study_timing": "Assessment behaviour",
        "assessment_participation": "Assessment behaviour",
        "deadline_adherence": "Assessment behaviour",
    }
    for tile in tiles:
        group = key_to_group.get(tile.get("key"))
        if group:
            groups[group].append(tile)
    return groups


def _render_behaviour_cards(tiles: list[dict]):
    if not tiles:
        render_empty_state(
            "Behavioural profile not available yet",
            "The Student page could not find this learner in the exported quarter behavioural tables.",
        )
        return

    grouped = _group_tiles(tiles)
    for section, section_tiles in grouped.items():
        if not section_tiles:
            continue
        st.markdown(f"#### {section}")
        for start in range(0, len(section_tiles), 3):
            cols = st.columns(3)
            for col, tile in zip(cols, section_tiles[start : start + 3]):
                title, definition = BEHAVIOUR_HELP.get(tile.get("key"), (tile.get("label", "Learning behaviour"), "Observed learning behaviour."))
                value_text = _tile_display_value(tile)
                status = str(tile.get("status") or "Observed")
                interpretation = STATUS_EXPLANATION.get(status, STATUS_EXPLANATION["Observed"])
                with col:
                    is_relative = value_text == "Relative indicator"
                    value_html = (
                        f"<div class='relative-indicator'>{escape(value_text)}</div>"
                        if is_relative
                        else f"<strong>{escape(value_text)}</strong>"
                    )
                    status_class = "primary-status" if is_relative else ""
                    st.markdown(
                        f"""
                        <div class='tw-habit tw-habit-{_behaviour_tone(status)}'>
                          <small>{escape(title)}</small>
                          {value_html}
                          <b class='{status_class}'>{escape(status)}</b>
                          <p>{escape(interpretation)}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    with st.expander("What does this mean?"):
                        st.caption(definition)


def _render_plain_language_interpretation(
    tiles: list[dict],
    strengths: list[str],
    opportunities: list[str],
    recommendations=None,
):
    st.markdown("### What your learning pattern is telling you")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**What is working well**")
        if strengths:
            for item in strengths[:3]:
                st.markdown(f"✓ {item}")
        else:
            st.caption("No clear strength has been classified yet at this checkpoint.")

    with c2:
        st.markdown("**What could improve**")
        normalised = [_normalise_recommendation(r) for r in (recommendations or [])]
        normalised = [r for r in normalised if r.get("title") or r.get("action")]

        if normalised:
            for rec in normalised[:3]:
                st.markdown(f"→ **{rec['title']}**")
                st.caption(f"{rec['why']}  Try this: {rec['action']}")
        elif opportunities:
            # Compatibility fallback for older exports that expose only broad opportunity labels.
            for item in opportunities[:3]:
                issue = str(item).strip()
                copy = RECOMMENDATION_COPY.get(issue)
                if copy:
                    st.markdown(f"→ **{copy['title']}**")
                    st.caption(f"{copy['why']}  Try this: {copy['action']}")
                else:
                    st.markdown(f"→ {item}")
        else:
            building = [t.get("label") for t in tiles if t.get("status") == "Building"][:3]
            if building:
                for item in building:
                    st.markdown(f"→ Keep building {item.lower()}.")
            else:
                st.caption("No meaningful corrective behavioural gap is visible at this checkpoint.")


# -----------------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------------


def _base_figure_layout(fig: go.Figure, *, x_title: str = "", y_title: str = "", height: int = 320):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=25, b=10),
        xaxis_title=x_title,
        yaxis_title=y_title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
        hovermode="x unified",
    )
    return fig


def _render_engagement_charts(student_id: int, module: str, presentation: str, quarter: str, cutoffs: dict):
    weekly, comparison, previous_average, bounds, dimensions_available = _engagement_current_quarter(
        student_id, module, presentation, quarter, cutoffs
    )
    start_week, end_week = bounds
    left, right = st.columns(2)

    with left:
        st.markdown("#### My Weekly Engagement – Current Quarter")
        previous_note = (
            " The dashed reference shows your average weekly **Overall Engagement** in the previous quarter."
            if previous_average is not None else ""
        )
        st.caption(
            f"Your actual VLE interactions during {quarter}, Weeks {start_week}–{end_week}."
            + previous_note
        )
        if weekly.empty:
            render_empty_state("Weekly engagement unavailable", "No VLE activity data are available for this class.")
        else:
            fig = go.Figure()
            if dimensions_available:
                for col in ["Course Materials", "Practice & Assessments", "Learning With Others"]:
                    if col in weekly.columns and pd.to_numeric(weekly[col], errors="coerce").notna().any():
                        fig.add_trace(go.Scatter(
                            x=weekly["week"],
                            y=pd.to_numeric(weekly[col], errors="coerce"),
                            mode="lines+markers",
                            name=col,
                            hovertemplate=f"Week %{{x}}<br>{col}: %{{y:,.0f}} interactions<extra></extra>",
                        ))
            fig.add_trace(go.Scatter(
                x=weekly["week"],
                y=weekly["Overall Engagement"],
                mode="lines+markers",
                name="Overall Engagement",
                line=dict(width=3),
                hovertemplate="Week %{x}<br>Overall Engagement: %{y:,.0f} interactions<extra></extra>",
            ))
            if previous_average is not None:
                fig.add_hline(
                    y=previous_average,
                    line_dash="dash",
                    annotation_text="Previous Quarter Avg – Overall",
                    annotation_position="top right",
                )
            _base_figure_layout(fig, x_title="Course week", y_title="VLE interactions")
            fig.update_xaxes(dtick=1)
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, key=f"engagement_self_{student_id}_{quarter}")

            if not dimensions_available:
                st.info(
                    "Overall Engagement is available, but content/assessment/social lines need `vle.csv` "
                    "activity-type metadata. Check that the dashboard can access the raw OULAD `vle.csv` file."
                )

    with right:
        st.markdown("#### ME vs Class Average")
        st.caption(
            f"Actual interaction totals during {quarter}, Weeks {start_week}–{end_week}. "
            "Class Average = total interactions from all enrolled students ÷ total students in this class."
        )
        if comparison.empty:
            render_empty_state("Class comparison unavailable", "Engagement totals could not be calculated for this class.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=comparison["Metric"],
                y=comparison["ME"],
                name="ME",
                text=comparison["ME"].map(lambda v: f"{v:,.0f}"),
                textposition="auto",
                hovertemplate="%{x}<br>ME: %{y:,.0f} interactions<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=comparison["Metric"],
                y=comparison["Class Average"],
                name="Class Average",
                text=comparison["Class Average"].map(lambda v: f"{v:,.1f}"),
                textposition="auto",
                hovertemplate="%{x}<br>Class Average: %{y:,.1f} interactions<extra></extra>",
            ))
            _base_figure_layout(fig, y_title="VLE interactions")
            fig.update_layout(barmode="group", hovermode="closest")
            st.plotly_chart(fig, use_container_width=True, key=f"engagement_compare_{student_id}_{quarter}")


def _render_consistency_charts(
    student_id: int,
    module: str,
    presentation: str,
    quarter: str,
    cutoffs: dict,
):
    """Render weekly consistency instead of a single quarter checkpoint dot."""
    progress, comparison, summary = _weekly_consistency_data(
        student_id, module, presentation, quarter, cutoffs
    )
    left, right = st.columns(2)

    with left:
        st.markdown("#### My Study Consistency This Quarter")
        if summary:
            st.caption(
                f"Weeks {summary['start_week']}–{summary['end_week']}. "
                "The line shows the percentage of available weeks you have been active so far; "
                "the markers show whether each individual week was active."
            )
        if progress.empty:
            render_empty_state(
                "Consistency trend unavailable",
                "Weekly VLE activity could not be calculated for this learner and class.",
            )
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=progress["week"],
                y=progress["Cumulative active weeks %"],
                mode="lines+markers",
                name="Active Weeks So Far",
                line=dict(width=3),
                hovertemplate=(
                    "Week %{x}<br>Active weeks so far: %{y:.1f}%<extra></extra>"
                ),
            ))

            # A second marker-only trace makes active/inactive weeks explicit.
            status_text = [
                "Active" if value > 0 else "No recorded activity"
                for value in progress["Active this week %"]
            ]
            fig.add_trace(go.Scatter(
                x=progress["week"],
                y=progress["Active this week %"],
                mode="markers",
                name="Weekly Activity Status",
                marker=dict(size=9, symbol="circle-open"),
                text=status_text,
                hovertemplate="Week %{x}<br>%{text}<extra></extra>",
            ))

            _base_figure_layout(
                fig,
                x_title="Course week",
                y_title="Active weeks so far (%)",
            )
            fig.update_yaxes(range=[0, 105], ticksuffix="%")
            fig.update_xaxes(dtick=1)
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"consistency_self_{student_id}_{quarter}",
            )

    with right:
        st.markdown("#### ME vs Class Average")
        st.caption(
            "Overall study consistency across the selected quarter. "
            "ME is the percentage of quarter weeks in which you were active. "
            "Class Average is the average active-week percentage across all enrolled "
            "students in the same module and presentation."
        )

        if not summary:
            render_empty_state(
                "Class comparison unavailable",
                "Quarter-level active-week values could not be calculated.",
            )
        else:
            me_pct = float(summary.get("student_pct", 0.0))
            class_pct = float(summary.get("class_pct", 0.0))
            quarter_weeks = int(summary.get("quarter_weeks", 0))
            me_active_weeks = int(summary.get("active_weeks", 0))
            class_avg_weeks = (class_pct / 100.0) * quarter_weeks if quarter_weeks else 0.0

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Quarter consistency"],
                y=[me_pct],
                name="ME",
                text=[f"{me_pct:.0f}%"],
                textposition="auto",
                customdata=[[me_active_weeks, quarter_weeks]],
                hovertemplate=(
                    "ME<br>Active weeks: %{customdata[0]:.0f} of %{customdata[1]:.0f}"
                    "<br>Consistency: %{y:.1f}%<extra></extra>"
                ),
            ))
            fig.add_trace(go.Bar(
                x=["Quarter consistency"],
                y=[class_pct],
                name="Class Average",
                text=[f"{class_pct:.0f}%"],
                textposition="auto",
                customdata=[[class_avg_weeks, quarter_weeks]],
                hovertemplate=(
                    "Class Average<br>Average active weeks: %{customdata[0]:.1f} of %{customdata[1]:.0f}"
                    "<br>Consistency: %{y:.1f}%<extra></extra>"
                ),
            ))

            _base_figure_layout(
                fig,
                y_title="Active weeks (%)",
            )
            fig.update_yaxes(range=[0, 105], ticksuffix="%")
            fig.update_layout(
                barmode="group",
                hovermode="closest",
                xaxis_title=None,
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"consistency_compare_{student_id}_{quarter}",
            )


    if summary:
        inactive = summary.get("inactive_weeks", [])
        if inactive:
            gap_text = ", ".join(f"Week {w}" for w in inactive)
            st.info(
                f"You were active in **{summary['active_weeks']} of {summary['quarter_weeks']} weeks** "
                f"this quarter ({summary['student_pct']:.0f}%). The class average across the same "
                f"quarter is **{summary['class_pct']:.0f}% active weeks**. "
                f"No activity was recorded in {gap_text}."
            )
        else:
            st.success(
                f"You were active in **all {summary['quarter_weeks']} weeks** this quarter. "
                f"The class average across the same quarter is **{summary['class_pct']:.0f}% active weeks**."
            )


def _render_assessment_charts(student_id: int, module: str, presentation: str, end_week: int):
    details, comparison, _ = _assessment_data(student_id, module, presentation, end_week)
    left, right = st.columns(2)

    with left:
        st.markdown("#### My assessment progress")
        st.caption("Your available assessment scores in chronological order up to this checkpoint.")
        scored = details.dropna(subset=["score"]) if not details.empty else pd.DataFrame()
        if scored.empty:
            render_empty_state("Assessment progress unavailable", "No submitted assessment score is available by this checkpoint.")
        else:
            fig = go.Figure(go.Scatter(x=scored["Assessment"], y=scored["score"], mode="lines+markers", name="My score"))
            _base_figure_layout(fig, x_title="Assessment", y_title="Score (%)")
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True, key=f"assessment_self_{student_id}_{end_week}")

    with right:
        st.markdown("#### ME vs Class Average")
        st.caption("Your score compared with the average score recorded for the same assessment in the same class (module and presentation).")
        if comparison.empty:
            render_empty_state("Assessment comparison unavailable", "No assessment comparison data are available by this checkpoint.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=comparison["Assessment"], y=comparison["My score"], name="My score"))
            fig.add_trace(go.Bar(x=comparison["Assessment"], y=comparison["Class average"], name="Class average"))
            _base_figure_layout(fig, x_title="Assessment", y_title="Score (%)")
            fig.update_yaxes(range=[0, 100])
            fig.update_layout(barmode="group", hovermode="closest")
            st.plotly_chart(fig, use_container_width=True, key=f"assessment_compare_{student_id}_{end_week}")


# -----------------------------------------------------------------------------
# Priority recommendation block
# -----------------------------------------------------------------------------

PRIORITY_RECOMMENDATION_COPY = {
    "assessment timing opportunity": (
        "Start your next assessment earlier by choosing a personal start date several days before you would normally begin. "
        "Use that extra time to review the instructions, ask questions and revise before submission."
    ),
    "deadline planning opportunity": (
        "Plan upcoming assessment deadlines in advance by adding the next due date to your calendar and setting an earlier personal reminder, "
        "so you have enough time to complete and review the work without last-minute pressure."
    ),
    "assessment practice opportunity": (
        "Build more assessment practice into your study routine by completing at least one available quiz or self-check activity this week, "
        "then use the result to identify topics that need further review."
    ),
    "course material engagement opportunity": (
        "Reconnect with the core course materials before your next study or assessment session by reviewing the key resource for the upcoming topic, "
        "then use it to guide your practice."
    ),
    "study spacing opportunity": (
        "Spread your study across two or three shorter sessions on different days this week instead of concentrating your activity into one long burst, "
        "so learning is reinforced more regularly."
    ),
    "study consistency opportunity": (
        "Build a steadier weekly routine by scheduling three small study windows this week—even 15–30 minutes each—so you stay connected to the course "
        "and prevent work from accumulating."
    ),
    "peer learning opportunity": (
        "Increase your participation in collaborative learning by reading the current discussion and contributing one question, reply or useful comment this week, "
        "giving you another way to test and clarify your understanding."
    ),
}


def _priority_recommendation_payload(recs, fallback_issue="") -> tuple[str, str, str]:
    """Return gap label, plain-language action and supporting reason for the top recommendation."""
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
            f"Focus on strengthening {focus} during the next study period by choosing one small, specific action and repeating it consistently before the next checkpoint."
        )
    else:
        recommendation = (
            "No corrective behavioural gap currently crosses the recommendation threshold. Continue the learning habits that are working and keep checking in regularly before the next checkpoint."
        )

    gap_label = issue if issue else "No priority behavioural gap"
    return gap_label, recommendation, why


def _render_priority_recommendation_block(recs, fallback_issue="", audience="student"):
    gap, recommendation, why = _priority_recommendation_payload(recs, fallback_issue)
    heading = "Your priority recommendation" if audience == "student" else "Priority recommendation for this learner"
    reason_html = (
        f"<div class='reason'><b>Why this is prioritised:</b> {escape(why)}</div>"
        if why else ""
    )
    st.markdown(
        f"""
        <div class='tw-priority-rec'>
          <div class='eyebrow'>{escape(heading)}</div>
          <div class='gap'>Prioritised behavioural gap: {escape(gap)}</div>
          <div class='recommendation'>{escape(recommendation)}</div>
          {reason_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Recommendation copy + schema compatibility
# -----------------------------------------------------------------------------

RECOMMENDATION_COPY = {
    "Assessment timing opportunity": {
        "area": "Assessment behaviour",
        "title": "Give yourself an earlier start",
        "why": "Your recent assessment work has tended to happen closer to the deadline than the historical successful-peer benchmark.",
        "why_it_matters": "Starting earlier gives you more time to review instructions, ask questions and revise before the next task.",
        "action": "Choose one upcoming assessment and set a personal start date several days before you would normally begin.",
    },
    "Deadline planning opportunity": {
        "area": "Assessment behaviour",
        "title": "Plan around upcoming deadlines",
        "why": "Some recent submissions have gone beyond the scheduled deadline.",
        "why_it_matters": "A simple deadline plan can reduce last-minute pressure and help spread your study time.",
        "action": "Add the next assessment deadline to your calendar and set a personal reminder one or two days earlier.",
    },
    "Assessment practice opportunity": {
        "area": "Assessment behaviour",
        "title": "Use more practice and self-check activities",
        "why": "Your current pattern shows less assessment-related practice than the historical successful-peer benchmark.",
        "why_it_matters": "Practice activities can reveal topics that need another look before assessed work.",
        "action": "Choose one available quiz or self-check activity to complete this week.",
    },
    "Course material engagement opportunity": {
        "area": "Course materials",
        "title": "Reconnect with key course materials",
        "why": "Your current use of course materials is below the historical successful-peer benchmark for this learning context.",
        "why_it_matters": "Revisiting core materials can strengthen understanding before practice or assessed work.",
        "action": "Review the main resource linked to your next topic or assessment before your next study session.",
    },
    "Study spacing opportunity": {
        "area": "Study regularity",
        "title": "Spread your study across the week",
        "why": "Your recent learning activity is more concentrated into short bursts than the successful-peer benchmark.",
        "why_it_matters": "Shorter sessions spread across the week can make the workload more manageable and keep ideas active.",
        "action": "Plan two or three shorter sessions on different days instead of relying on one long session.",
    },
    "Study consistency opportunity": {
        "area": "Study consistency",
        "title": "Build a steadier weekly routine",
        "why": "You have been active in fewer course weeks than the historical successful-peer benchmark for this learning context.",
        "why_it_matters": "Regular check-ins make it easier to notice new tasks and prevent work from accumulating.",
        "action": "Choose three small study windows this week, even if each is only 15–30 minutes.",
    },
    "Peer learning opportunity": {
        "area": "Participation",
        "title": "Connect with your learning community",
        "why": "Your recent use of discussion and collaborative activities is below the historical successful-peer benchmark.",
        "why_it_matters": "Discussion gives you another way to test ideas, compare approaches and ask for clarification.",
        "action": "Read the current discussion thread and add one question, reply or useful comment.",
    },
}


def _first_rec_value(rec: dict, keys, default=""):
    if not isinstance(rec, dict):
        return default
    for key in keys:
        value = rec.get(key)
        if value is not None and str(value).strip() and str(value).strip().lower() != "nan":
            return value
    return default


def _normalise_recommendation(rec: dict) -> dict:
    """Accept both the old dashboard schema and the richer recommendation-pipeline schema."""
    rec = rec if isinstance(rec, dict) else {}
    issue = str(_first_rec_value(rec, ["issue_label", "issue", "main_opportunity"], "")).strip()
    fallback = RECOMMENDATION_COPY.get(issue, {})

    return {
        "priority": _first_rec_value(rec, ["priority", "rank"], ""),
        "issue_label": issue,
        "category": _first_rec_value(rec, ["category", "area"], fallback.get("area", "Learning support")),
        "title": _first_rec_value(rec, ["title", "recommendation_title"], fallback.get("title", "Suggested next step")),
        "why": _first_rec_value(
            rec,
            ["why", "explanation", "detail", "what_we_noticed"],
            fallback.get("why", "A learning behaviour could be strengthened."),
        ),
        "why_it_matters": _first_rec_value(
            rec,
            ["why_it_matters", "benefit", "rationale"],
            fallback.get("why_it_matters", "A small change here may make your learning routine easier to sustain."),
        ),
        "action": _first_rec_value(
            rec,
            ["action", "suggested_action", "next_step"],
            fallback.get("action", "Choose one small action for this week."),
        ),
    }

# -----------------------------------------------------------------------------
# Recommendations
# -----------------------------------------------------------------------------


def _recommendation_cards(recs, key_prefix="recommendation", student_id=None, quarter=None):
    if not recs:
        render_empty_state(
            "No corrective recommendation needed",
            "No meaningful behavioural gap crossed the recommendation threshold for this course stage. Keep your current routine and check back at the next checkpoint.",
        )
        return

    for idx, raw_rec in enumerate(recs, 1):
        rec = _normalise_recommendation(raw_rec)
        st.markdown(
            f"""
            <div class='tw-rec'>
              <span class='num'>{idx}</span><span class='tw-chip'>{escape(str(rec['category']))}</span>
              <h3>{escape(str(rec['title']))}</h3>
              <p><b>What we noticed.</b> {escape(str(rec['why']))}</p>
              <p><b>Why it matters.</b> {escape(str(rec['why_it_matters']))}</p>
              <div class='action'><b>Try this:</b> {escape(str(rec['action']))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        safe_title = str(rec.get("title", "recommendation")).replace(" ", "_")
        button_key = f"{key_prefix}_{student_id}_{quarter}_{idx}_{safe_title}"
        if st.button("Add to my plan", key=button_key, use_container_width=False):
            plan = st.session_state.setdefault("student_plan", [])
            if rec.get("action") not in plan:
                plan.append(rec.get("action"))
                st.toast("Added to your study plan")
            else:
                st.toast("This action is already in your study plan")


# -----------------------------------------------------------------------------
# Main Student page
# -----------------------------------------------------------------------------


def render_student_dashboard(user):
    require_role(user, "student")
    _inject_student_status_styles()
    student_id = int(user["student_id"])
    module = str(user["module"])
    presentation = str(user["presentation"])

    info = load_student_info()
    if not can_access_module(user, module, presentation) or not can_access_student(
        user, student_id, module, presentation, student_info=info
    ):
        st.error("Your assigned learner record is unavailable.")
        st.stop()

    profile = _profile_row(info, student_id, module, presentation)
    render_page_heading(
        "My learning dashboard",
        f"Student ID {student_id} · {module} · {presentation}",
    )

    # Top ribbon: real Student ID + course context + checkpoint.
    with ribbon_start("Student & course context"):
        c1, c2, c3, c4 = st.columns([1.4, 1.8, 1.6, 2.2])
        with c1:
            _context_block("Student ID", str(student_id))
        with c2:
            _context_block("Module", module)
        with c3:
            _context_block("Presentation", presentation)
        with c4:
            quarter = st.selectbox(
                "Course stage",
                QUARTERS,
                format_func=lambda q: QUARTER_LABELS.get(q, q),
                index=1,
                key="student_quarter",
            )

    cutoffs = _course_cutoffs(module, presentation, quarter)
    end_week = _quarter_end_week(cutoffs, quarter)
    course_weeks = int(cutoffs.get("course_weeks", cutoffs.get("q4_end", end_week)))

    # Demographic/course details are visible to the learner, but final_result is intentionally omitted.
    st.markdown("### Student details")
    detail_cols = st.columns(4)
    detail_items = [
        ("Gender", profile.get("gender", "—")),
        ("Age band", profile.get("age_band", "—")),
        ("Highest education", profile.get("highest_education", "—")),
        ("Region", profile.get("region", "—")),
        ("Studied credits", profile.get("studied_credits", "—")),
        ("Previous attempts", profile.get("num_of_prev_attempts", "—")),
        ("Course length", f"{course_weeks} weeks"),
    ]
    for idx, (label, value) in enumerate(detail_items):
        with detail_cols[idx % 4]:
            render_metric_card(label, str(value), "")


    status = analytics_status(quarter)
    st.caption(
        f"Viewing data available up to **Week {end_week}** of this {course_weeks}-week presentation. "
        + ("Behavioural recommendations are connected." if status.get("recommendations") else "Recommendation output is not available for this learner/checkpoint.")
    )

    # Prominent but supportive three-level learning-support status.
    front_summary = student_recommendation_row(student_id, module, presentation, quarter)
    status_title, status_message, status_tone = _student_support_view(front_summary)
    _render_learning_support_status(
        status_title,
        status_message,
        status_tone,
    )

    # Make the top-ranked behavioural recommendation explicit and actionable.
    priority_recs = student_recommendations(
        student_id, module, presentation, quarter, limit=3
    )
    _render_priority_recommendation_block(priority_recs, audience="student")

    # Exact requested navigation: only three Student tabs.
    tabs = st.tabs(["My Learning", "Assessments", "Recommendations"])

    # ------------------------------------------------------------------
    # TAB 1: My Learning
    # ------------------------------------------------------------------
    with tabs[0]:
        st.subheader("My behavioural learning indicators")
        st.caption(
            "These indicators describe how you are engaging, how consistently you are studying, and how you are approaching assessments. They are behavioural signals—not grades or permanent learner labels."
        )

        tiles = student_behaviour_tiles(student_id, module, presentation, quarter)
        existing_keys = {t.get("key") for t in tiles}
        tiles = list(tiles) + _supplemental_tiles(student_id, module, presentation, quarter, existing_keys)
        visible_keys = {
            "overall_engagement", "course_materials", "assessment_engagement", "social_engagement",
            "study_consistency", "study_timing", "assessment_participation", "deadline_adherence",
        }
        tiles = [t for t in tiles if t.get("key") in visible_keys]
        strengths, opportunities = student_strengths_opportunities(tiles)
        learning_recs = priority_recs

        _render_behaviour_cards(tiles)
        st.divider()
        _render_plain_language_interpretation(
            tiles, strengths, opportunities, recommendations=learning_recs
        )

        st.divider()
        st.markdown("### Explore my progress")
        st.caption(
            "Choose a learning area. Engagement shows your week-by-week activity inside the selected quarter and a direct ME vs Class Average comparison."
        )
        progress_view = st.radio(
            "Learning area",
            ["Engagement", "Consistency", "Assessment"],
            horizontal=True,
            label_visibility="collapsed",
            key="student_progress_view",
        )

        if progress_view == "Engagement":
            _render_engagement_charts(student_id, module, presentation, quarter, cutoffs)
        elif progress_view == "Consistency":
            _render_consistency_charts(student_id, module, presentation, quarter, cutoffs)
        else:
            _render_assessment_charts(student_id, module, presentation, end_week)

        with st.expander("How should I interpret these comparisons?"):
            st.markdown(
                """
                - **My progress** is a within-student view: it helps you see change across weeks, assessments or checkpoints.
                - **Class average** includes learners from the same class (module and presentation) only; it is context, not a target you must beat.
                - Behavioural indicators are intended to support reflection and action. They do not determine your final grade.
                """
            )

    # ------------------------------------------------------------------
    # TAB 2: Assessments
    # ------------------------------------------------------------------
    with tabs[1]:
        st.subheader("My assessments")
        st.caption(
            f"Assessment information available by Week {end_week}. Scores or submissions made after this checkpoint are intentionally not shown in this historical view."
        )
        details, comparison, next_assessment = _assessment_data(student_id, module, presentation, end_week)

        if details.empty:
            render_empty_state(
                "Assessment information unavailable",
                "No assessment with a recorded due date is available for this learner by the selected checkpoint.",
            )
        else:
            submitted = details["date_submitted"].notna()
            scored = details["score"].notna()
            on_time = submitted & details["days_before_deadline"].ge(0)
            avg_score = details.loc[scored, "score"].mean()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                render_metric_card("Submitted", f"{int(submitted.sum())} / {len(details)}", "Due by this checkpoint")
            with c2:
                render_metric_card("Average score", f"{avg_score:.0f}%" if pd.notna(avg_score) else "—", "Available submitted assessments")
            with c3:
                render_metric_card("On time", f"{int(on_time.sum())} / {int(submitted.sum())}" if submitted.any() else "0 / 0", "Submitted on/before deadline")
            with c4:
                if next_assessment:
                    next_week = int(math.ceil(float(next_assessment["date"]) / 7))
                    render_metric_card("Next assessment", f"Week {next_week}", str(next_assessment.get("assessment_type", "Assessment")).upper())
                else:
                    render_metric_card("Next assessment", "—", "No later dated assessment found")

            display = details[["Assessment", "assessment_type", "Due week", "Submitted week", "Timing", "score", "weight"]].copy()
            display = display.rename(columns={
                "assessment_type": "Type",
                "score": "Score %",
                "weight": "Weight %",
            })
            st.markdown("#### Assessment details")
            st.dataframe(display, hide_index=True, use_container_width=True)

            st.markdown("#### Submission timing")
            timing = details.dropna(subset=["date_submitted"]).copy()
            if timing.empty:
                st.caption("No submitted assessment is available for a timing chart at this checkpoint.")
            else:
                fig = go.Figure(go.Bar(
                    x=timing["Assessment"],
                    y=timing["days_before_deadline"],
                    text=timing["Timing"],
                    textposition="auto",
                ))
                fig.add_hline(y=0, line_dash="dash", annotation_text="Deadline")
                _base_figure_layout(fig, x_title="Assessment", y_title="Days before deadline")
                fig.update_layout(showlegend=False, hovermode="closest")
                st.plotly_chart(fig, use_container_width=True, key=f"assessment_timing_{student_id}_{quarter}")

            st.markdown("#### Class score distribution by assessment")
            st.caption(
                "Each box shows the distribution of class scores recorded for that assessment by this checkpoint. "
                "The diamond marker shows your score when you had submitted the assessment by this checkpoint."
            )

            score_distribution, student_scores = _assessment_boxplot_data(
                student_id, module, presentation, end_week
            )

            if score_distribution.empty:
                st.caption("No class score distribution is available for the assessments due by this checkpoint.")
            else:
                fig = go.Figure()

                # One class-distribution box per assessment.
                fig.add_trace(go.Box(
                    x=score_distribution["Assessment"],
                    y=score_distribution["score"],
                    name="Class score distribution",
                    boxpoints="outliers",
                    hovertemplate=(
                        "%{x}<br>Class score: %{y:.1f}%<extra>Class distribution</extra>"
                    ),
                ))

                submitted_scores = student_scores.dropna(subset=["score"]).copy()
                if not submitted_scores.empty:
                    fig.add_trace(go.Scatter(
                        x=submitted_scores["Assessment"],
                        y=submitted_scores["score"],
                        mode="markers",
                        name="My score",
                        marker=dict(size=12, symbol="diamond"),
                        hovertemplate=(
                            "%{x}<br>My score: %{y:.1f}%<extra></extra>"
                        ),
                    ))

                _base_figure_layout(fig, x_title="Assessment", y_title="Score (%)", height=360)
                fig.update_yaxes(range=[0, 100])
                fig.update_layout(hovermode="closest")
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"assessment_tab_boxplot_{student_id}_{quarter}",
                )

            if not student_scores.empty:
                not_submitted = student_scores[student_scores["date_submitted"].isna()]["Assessment"].tolist()
                if not_submitted:
                    assessment_list = ", ".join(not_submitted)
                    st.warning(
                        f"**Assessment not submitted at this checkpoint:** {assessment_list}. "
                        "No personal score marker is shown for these assessments. "
                        "The box plot still shows the available class score distribution for context."
                    )

    # ------------------------------------------------------------------
    # TAB 3: Recommendations
    # ------------------------------------------------------------------
    with tabs[2]:
        st.subheader("My personalised recommendations")
        st.caption(
            "TrackWise shows at most three focused actions. Recommendations are generated from meaningful behavioural gaps against historical successful-peer reference patterns and are suggestions—not automated academic decisions."
        )

        summary = student_recommendation_row(student_id, module, presentation, quarter)
        recs = priority_recs

        if summary:
            visible_support, _, _ = _student_support_view(summary)
            st.info(f"**Current learning-support status:** {visible_support}")

        _recommendation_cards(
            recs,
            key_prefix="recommendations",
            student_id=student_id,
            quarter=quarter,
        )

        st.divider()
        st.markdown("### My study plan")
        plan = [item for item in st.session_state.get("student_plan", []) if item]
        if not plan:
            st.caption("Add a recommendation to your plan when you want to turn it into a concrete action.")
        else:
            for i, action in enumerate(plan, 1):
                st.checkbox(
                    action,
                    key=f"student_plan_{student_id}_{quarter}_{i}",
                )

        st.info(
            "This is a research demonstration using historical anonymised OULAD data. The dashboard does not contact a tutor, submit an assessment, or make an automated academic decision."
        )
