"""
TrackWise — Instructor Dashboard
Every student, at a glance. Click any student to see their full story.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="Class View · TrackWise", layout="wide", page_icon="👩‍🏫")

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; background: #0c0e18; color: #e8eaf0; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1220 0%, #0c0e18 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
header[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 1.5rem !important; }

.kpi-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
}
.kpi-num {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    line-height: 1;
    margin-bottom: 4px;
}
.kpi-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: .05em; }
.kpi-sub   { font-size: 0.8rem; margin-top: 5px; font-weight: 500; }

.section-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.4rem; color: #e8eaf0; margin: 1.8rem 0 .8rem;
}

.student-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 16px 18px;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 8px;
}
.student-card:hover {
    background: rgba(255,255,255,0.07);
    border-color: rgba(129,140,248,0.3);
}

.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
}

.action-card {
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 10px;
    border-left: 3px solid;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    DATA = Path("data")
    try:
        si  = pd.read_csv(DATA / "studentInfo.csv")
        vle = pd.read_csv(DATA / "studentVle.csv")
        sa  = pd.read_csv(DATA / "studentAssessment.csv")
        ass = pd.read_csv(DATA / "assessments.csv")
        return si, vle, sa, ass
    except:
        return None, None, None, None

si, vle_df, sa, ass = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:8px 0 20px'>
        <div style='font-family:"DM Serif Display",serif;font-size:1.6rem;color:#e8eaf0'>TrackWise</div>
        <div style='font-size:0.8rem;color:#475569;margin-top:2px'>Instructor View</div>
    </div>""", unsafe_allow_html=True)

    if si is not None:
        modules  = sorted(si["code_module"].unique())
        module   = st.selectbox("Module", modules)
        pres_opts = sorted(si[si["code_module"]==module]["code_presentation"].unique())
        pres     = st.selectbox("Presentation", pres_opts)
        cohort   = si[(si["code_module"]==module) & (si["code_presentation"]==pres)].copy()
    else:
        module, pres = "BBB", "2014J"
        cohort = pd.DataFrame()

    st.markdown("---")
    quarter = st.selectbox("📅 Course Stage",
        ["Q1 — Early", "Q2 — Mid-point", "Q3 — Late", "Q4 — Final"], index=1)
    quarter_key = quarter[:2]

    filter_risk = st.multiselect("Show students by status",
        ["🔴 Urgent", "🟡 Watch", "🟢 On Track"],
        default=["🔴 Urgent", "🟡 Watch", "🟢 On Track"])

    sort_by = st.selectbox("Sort by", ["Risk (highest first)", "Score (lowest first)", "Engagement (lowest first)"])
    st.markdown("---")
    st.markdown("<div style='font-size:0.75rem;color:#334155'>TrackWise Analytics</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BUILD COHORT METRICS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def build_cohort_table(module, pres, _si, _vle_df, _sa, _ass):
    if _si is None:
        return pd.DataFrame()

    cohort = _si[(_si["code_module"]==module) & (_si["code_presentation"]==pres)].copy()
    if cohort.empty:
        return cohort

    cohort["at_risk"] = cohort["final_result"].isin(["Fail","Withdrawn"]).astype(int)

    # ── VLE engagement per student ──────────────────────────────────────────
    if _vle_df is not None:
        vle_mod = _vle_df[
            (_vle_df["code_module"]==module) &
            (_vle_df["code_presentation"]==pres)
        ].copy()
        vle_mod["date"]      = pd.to_numeric(vle_mod["date"],      errors="coerce").fillna(0)
        vle_mod["sum_click"] = pd.to_numeric(vle_mod["sum_click"], errors="coerce").fillna(0)
        vle_mod["week"]      = (vle_mod["date"].clip(lower=0) // 7) + 1
        total_weeks_val      = int(vle_mod["week"].max()) if not vle_mod.empty else 20

        eng = vle_mod.groupby("id_student").agg(
            total_clicks=("sum_click", "sum"),
            active_weeks=("week",      lambda x: x.nunique())
        ).reset_index()
        cohort = cohort.merge(eng, on="id_student", how="left")
        cohort["total_clicks"]   = pd.to_numeric(cohort["total_clicks"],  errors="coerce").fillna(0).astype(int)
        cohort["active_weeks"]   = pd.to_numeric(cohort["active_weeks"],  errors="coerce").fillna(0).astype(int)
        cohort["activity_ratio"] = cohort["active_weeks"] / max(total_weeks_val, 1)
    else:
        cohort["total_clicks"]   = np.random.randint(200, 3000, len(cohort))
        cohort["active_weeks"]   = np.random.randint(2,   18,   len(cohort))
        cohort["activity_ratio"] = cohort["active_weeks"] / 20

    # ── Assessment scores ───────────────────────────────────────────────────
    if _sa is not None and _ass is not None:
        ass_mod = _ass[
            (_ass["code_module"]==module) &
            (_ass["code_presentation"]==pres) &
            (_ass["assessment_type"]!="Exam")
        ].copy()

        scores = _sa.merge(ass_mod[["id_assessment", "date"]], on="id_assessment", how="inner")

        # *** FIX: force score to numeric before any aggregation ***
        scores["score"] = pd.to_numeric(scores["score"], errors="coerce")

        avg_scores = scores.groupby("id_student")["score"].mean().reset_index()
        avg_scores.columns = ["id_student", "avg_score"]

        # late submissions — is_banked == 0 means submitted late
        if "is_banked" in scores.columns:
            scores["is_banked"] = pd.to_numeric(scores["is_banked"], errors="coerce").fillna(1)
            late = (
                scores.groupby("id_student")["is_banked"]
                .apply(lambda x: (x == 0).sum())
                .reset_index()
            )
            late.columns = ["id_student", "late_count"]
        else:
            late = pd.DataFrame({"id_student": scores["id_student"].unique(), "late_count": 0})

        cohort = cohort.merge(avg_scores, on="id_student", how="left")
        cohort = cohort.merge(late,       on="id_student", how="left")

        # safe guard — column must exist after merge
        if "avg_score" not in cohort.columns:
            cohort["avg_score"] = np.nan
        if "late_count" not in cohort.columns:
            cohort["late_count"] = 0

        cohort["avg_score"]  = pd.to_numeric(cohort["avg_score"],  errors="coerce")
        cohort["late_count"] = pd.to_numeric(cohort["late_count"], errors="coerce").fillna(0).astype(int)
    else:
        cohort["avg_score"]  = np.random.normal(60, 15, len(cohort)).clip(0, 100).round(1)
        cohort["late_count"] = np.random.randint(0, 4, len(cohort))

    # ── Risk tier ───────────────────────────────────────────────────────────
    def assign_tier(row):
        ar = float(row.get("activity_ratio", 0) or 0)
        sc = float(row.get("avg_score",      50) or 50)
        lc = int(  row.get("late_count",      0) or 0)
        if ar < 0.3  or sc < 45 or lc >= 3: return "🔴 Urgent"
        if ar < 0.55 or sc < 58 or lc >= 2: return "🟡 Watch"
        return "🟢 On Track"

    cohort["status"] = cohort.apply(assign_tier, axis=1)
    cohort["health"] = (
        (cohort["activity_ratio"].fillna(0) * 50) +
        (cohort["avg_score"].fillna(50) / 100 * 50)
    ).clip(0, 100).round(0).astype(int)

    return cohort

cohort_table = build_cohort_table(module, pres, si, vle_df, sa, ass)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='margin-bottom:1.5rem'>
    <div style='font-size:0.9rem;color:#475569;font-weight:500'>Instructor Dashboard</div>
    <div style='font-family:"DM Serif Display",serif;font-size:2.2rem;color:#e8eaf0;line-height:1.2'>
        {module} · <span style='color:#818cf8'>{pres}</span>
    </div>
    <div style='font-size:0.9rem;color:#475569;margin-top:4px'>
        {len(cohort_table):,} students enrolled · {quarter_key} view
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CLASS KPI CARDS
# ─────────────────────────────────────────────────────────────────────────────
if not cohort_table.empty:
    n_urgent  = int((cohort_table["status"]=="🔴 Urgent").sum())
    n_watch   = int((cohort_table["status"]=="🟡 Watch").sum())
    n_ok      = int((cohort_table["status"]=="🟢 On Track").sum())
    n_total   = len(cohort_table)
    avg_score = cohort_table["avg_score"].mean()
    avg_score_display = f"{avg_score:.1f}%" if pd.notna(avg_score) else "N/A"
    withdrawal_rate = cohort_table["final_result"].eq("Withdrawn").mean() * 100

    kpi_data = [
        (f"{n_total}",           "Total Students",   "",                        "#818cf8"),
        (f"{n_urgent}",          "Need Urgent Help", f"{n_urgent/n_total*100:.0f}% of class", "#ef4444"),
        (f"{n_watch}",           "Worth Watching",   f"{n_watch/n_total*100:.0f}% of class",  "#f59e0b"),
        (avg_score_display,      "Class Avg Score",  "Across all assessments",  "#34d399"),
        (f"{withdrawal_rate:.1f}%","Withdrawal Rate","Students who left",        "#94a3b8"),
    ]
    cols = st.columns(5)
    for col, (num, lbl, sub, color) in zip(cols, kpi_data):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-num" style="color:{color}">{num}</div>
                <div class="kpi-label">{lbl}</div>
                <div class="kpi-sub" style="color:{color}88">{sub}</div>
            </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CLASS OVERVIEW CHARTS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Class Overview</div>', unsafe_allow_html=True)

col_dist, col_scatter = st.columns(2)

with col_dist:
    if not cohort_table.empty and "avg_score" in cohort_table.columns:
        scores_clean = cohort_table["avg_score"].dropna()
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=scores_clean, nbinsx=20,
            marker_color="#818cf8", marker_line_color="rgba(0,0,0,0)",
            opacity=0.8, name="All students"))
        fig_hist.add_vrect(x0=0, x1=50, fillcolor="rgba(239,68,68,0.08)",
                           line_width=0, annotation_text="Fail zone",
                           annotation_font_color="#ef4444", annotation_position="top left")
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", family="DM Sans"),
            title=dict(text="Score Distribution", font=dict(color="#e8eaf0")),
            xaxis=dict(title="Score (%)", gridcolor="rgba(255,255,255,0.04)"),
            yaxis=dict(title="Students",  gridcolor="rgba(255,255,255,0.04)"),
            bargap=0.05, height=280, showlegend=False, margin=dict(t=35,b=10,l=5,r=5))
        st.plotly_chart(fig_hist, use_container_width=True)

with col_scatter:
    if not cohort_table.empty:
        color_map = {"🔴 Urgent":"#ef4444","🟡 Watch":"#f59e0b","🟢 On Track":"#10b981"}
        scatter_df = cohort_table.dropna(subset=["avg_score","total_clicks"])
        if not scatter_df.empty:
            fig_sc = px.scatter(
                scatter_df.sample(min(500, len(scatter_df))),
                x="total_clicks", y="avg_score",
                color="status", color_discrete_map=color_map,
                opacity=0.7,
                labels={"total_clicks":"Total Clicks","avg_score":"Avg Score (%)","status":"Status"},
                title="Engagement vs Score")
            fig_sc.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8", family="DM Sans"),
                title=dict(font=dict(color="#e8eaf0")),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
                legend=dict(bgcolor="rgba(0,0,0,0)", title=""),
                height=280, margin=dict(t=35,b=10,l=5,r=5))
            st.plotly_chart(fig_sc, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# STUDENT TABLE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">👥 All Students</div>', unsafe_allow_html=True)

if not cohort_table.empty:
    display_table = cohort_table[cohort_table["status"].isin(filter_risk)].copy()

    if sort_by == "Risk (highest first)":
        sort_order = {"🔴 Urgent":0,"🟡 Watch":1,"🟢 On Track":2}
        display_table["sort_key"] = display_table["status"].map(sort_order)
        display_table = display_table.sort_values("sort_key")
    elif sort_by == "Score (lowest first)":
        display_table = display_table.sort_values("avg_score", ascending=True)
    else:
        display_table = display_table.sort_values("total_clicks", ascending=True)

    st.caption(f"Showing {len(display_table)} of {len(cohort_table)} students")

    table_display = display_table[["id_student","status","avg_score","active_weeks",
                                    "total_clicks","late_count","health","final_result"]].copy()
    table_display.columns = ["Student ID","Status","Avg Score (%)","Active Weeks",
                              "Total Clicks","Late Submissions","Health Score","Outcome"]
    table_display["Avg Score (%)"] = pd.to_numeric(table_display["Avg Score (%)"], errors="coerce").round(1)

    st.dataframe(
        table_display,
        use_container_width=True,
        hide_index=True,
        height=min(600, 40 + len(display_table) * 35),
        column_config={
            "Status":           st.column_config.TextColumn(width="medium"),
            "Health Score":     st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "Avg Score (%)":    st.column_config.NumberColumn(format="%.1f%%"),
            "Active Weeks":     st.column_config.NumberColumn(),
            "Total Clicks":     st.column_config.NumberColumn(),
            "Late Submissions": st.column_config.NumberColumn(),
        }
    )

# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL STUDENT DRILL-DOWN
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">🔍 Individual Student Deep Dive</div>', unsafe_allow_html=True)
st.caption("Select any student to see their full activity profile and get recommended actions")

if not cohort_table.empty:
    student_ids = sorted(cohort_table["id_student"].tolist())
    sel_id = st.selectbox("Choose a student to investigate", student_ids,
                           format_func=lambda x: f"Student {x}")

    sel_row = cohort_table[cohort_table["id_student"]==sel_id].iloc[0]

    tier       = sel_row["status"]
    tier_color = {"🔴 Urgent":"#ef4444","🟡 Watch":"#f59e0b","🟢 On Track":"#10b981"}.get(tier,"#818cf8")
    tier_bg    = {"🔴 Urgent":"#2b0a0a","🟡 Watch":"#2b2000","🟢 On Track":"#0d2b22"}.get(tier,"#1a1a3e")

    avg_sc_val = sel_row.get("avg_score")
    avg_sc_str = f"{float(avg_sc_val):.0f}%" if pd.notna(avg_sc_val) else "N/A"

    st.markdown(f"""
    <div style='background:{tier_bg};border:1px solid {tier_color}30;border-radius:14px;
    padding:20px 24px;display:flex;align-items:center;gap:24px;margin-bottom:1rem'>
        <div>
            <div style='font-size:0.8rem;color:#475569;text-transform:uppercase;
            letter-spacing:.05em;margin-bottom:4px'>Student #{sel_id}</div>
            <div style='font-family:"DM Serif Display",serif;font-size:1.6rem;color:{tier_color}'>{tier}</div>
            <div style='font-size:0.85rem;color:#94a3b8;margin-top:4px'>
                {sel_row.get("gender","—")} · Age: {sel_row.get("age_band","—")} · 
                Education: {sel_row.get("highest_education","—")} · 
                Prev attempts: {sel_row.get("num_of_prev_attempts","0")}
            </div>
        </div>
        <div style='margin-left:auto;text-align:center'>
            <div style='font-family:"DM Serif Display",serif;font-size:2.5rem;color:{tier_color}'>{int(sel_row.get("health",0))}</div>
            <div style='font-size:0.75rem;color:#475569'>Health Score</div>
        </div>
        <div style='text-align:center'>
            <div style='font-family:"DM Serif Display",serif;font-size:2.5rem;color:#e8eaf0'>{avg_sc_str}</div>
            <div style='font-size:0.75rem;color:#475569'>Avg Score</div>
        </div>
        <div style='text-align:center'>
            <div style='font-family:"DM Serif Display",serif;font-size:2.5rem;color:#e8eaf0'>
                {int(sel_row.get("active_weeks",0))}</div>
            <div style='font-size:0.75rem;color:#475569'>Active Weeks</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_w, col_a = st.columns(2)

    with col_w:
        st.markdown("**Weekly Activity vs Class**")
        if vle_df is not None:
            s_vle = vle_df[(vle_df["id_student"]==sel_id) &
                           (vle_df["code_module"]==module) &
                           (vle_df["code_presentation"]==pres)].copy()
            c_vle = vle_df[(vle_df["code_module"]==module) &
                           (vle_df["code_presentation"]==pres)].copy()
            for df_ in [s_vle, c_vle]:
                df_["date"]      = pd.to_numeric(df_["date"],      errors="coerce").fillna(0)
                df_["sum_click"] = pd.to_numeric(df_["sum_click"], errors="coerce").fillna(0)
                df_["week"]      = (df_["date"].clip(lower=0) // 7) + 1

            sw     = s_vle.groupby("week")["sum_click"].sum().reset_index()
            cw     = (c_vle.groupby(["id_student","week"])["sum_click"].sum()
                          .reset_index()
                          .groupby("week")["sum_click"].mean()
                          .reset_index())
            merged = sw.merge(cw, on="week", how="outer",
                              suffixes=("_me","_class")).sort_values("week").fillna(0)

            fig_w = go.Figure()
            fig_w.add_trace(go.Bar(x=merged["week"], y=merged["sum_click_class"],
                marker_color="rgba(71,85,105,0.5)", name="Class Avg"))
            fig_w.add_trace(go.Bar(x=merged["week"], y=merged["sum_click_me"],
                marker_color=tier_color, opacity=0.85, name="This Student"))
            fig_w.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8", family="DM Sans"), barmode="overlay",
                xaxis=dict(title="Week", gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(title="Clicks", gridcolor="rgba(255,255,255,0.04)"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                height=230, margin=dict(t=5,b=10,l=5,r=5))
            st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.info("VLE data not available")

    with col_a:
        st.markdown("**Assessment Scores**")
        if sa is not None and ass is not None:
            ass_mod = ass[(ass["code_module"]==module) &
                          (ass["code_presentation"]==pres) &
                          (ass["assessment_type"]!="Exam")].copy()
            s_scores = (sa[sa["id_student"]==sel_id]
                        .merge(ass_mod[["id_assessment","date"]], on="id_assessment", how="inner")
                        .sort_values("date"))
            c_scores = sa.merge(ass_mod[["id_assessment","date"]], on="id_assessment", how="inner")
            c_scores["score"] = pd.to_numeric(c_scores["score"], errors="coerce")
            class_a  = c_scores.groupby("id_assessment")["score"].mean().reset_index()

            if not s_scores.empty:
                s_scores["score"] = pd.to_numeric(s_scores["score"], errors="coerce")
                s_scores["label"] = [f"T{i+1}" for i in range(len(s_scores))]
                class_a["label"]  = [f"T{i+1}" for i in range(len(class_a))]
                bar_colors = ["#10b981" if s>=60 else "#f59e0b" if s>=40 else "#ef4444"
                              for s in s_scores["score"].fillna(0)]
                fig_a = go.Figure()
                fig_a.add_trace(go.Bar(x=s_scores["label"], y=s_scores["score"],
                    marker_color=bar_colors, name="This Student", marker_line_width=0))
                fig_a.add_trace(go.Scatter(x=class_a["label"], y=class_a["score"],
                    mode="lines+markers", line=dict(color="#475569",dash="dot"),
                    marker=dict(size=5), name="Class Avg"))
                fig_a.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8", family="DM Sans"),
                    xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                    yaxis=dict(range=[0,105], title="Score (%)",
                               gridcolor="rgba(255,255,255,0.04)"),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    height=230, margin=dict(t=5,b=10,l=5,r=5))
                st.plotly_chart(fig_a, use_container_width=True)
            else:
                st.info("No assessment data for this student")
        else:
            st.info("Assessment data not available")

    # ── Recommended actions ──────────────────────────────────────────────────
    st.markdown("**🎯 Recommended Actions for the Instructor**")

    ar   = float(sel_row.get("activity_ratio", 0) or 0)
    sc   = float(sel_row.get("avg_score",      50) or 50)
    lc   = int(  sel_row.get("late_count",      0) or 0)

    instructor_actions = []

    if tier == "🔴 Urgent":
        instructor_actions.append({
            "color":  "#ef4444", "bg": "rgba(239,68,68,0.07)", "icon": "🚨",
            "action": "Contact this student immediately",
            "detail": f"Student #{sel_id} is at serious risk. Engagement is critically low "
                      f"({int(ar*100)}% of weeks active) and/or scores are in the failing range. "
                      f"A direct message this week could prevent withdrawal."
        })
    if sc < 55:
        instructor_actions.append({
            "color":  "#ef4444", "bg": "rgba(239,68,68,0.05)", "icon": "📉",
            "action": "Offer academic support or office hours",
            "detail": f"Average score ({sc:.0f}%) is well below the class average. "
                      f"Point them to specific resources for topics where they've struggled most."
        })
    if lc >= 2:
        instructor_actions.append({
            "color":  "#f59e0b", "bg": "rgba(245,158,11,0.07)", "icon": "⏰",
            "action": "Discuss deadline management",
            "detail": f"This student has {lc} late submissions. A brief conversation about time "
                      f"management or personal circumstances could reveal issues you can accommodate."
        })
    if ar < 0.4:
        instructor_actions.append({
            "color":  "#f59e0b", "bg": "rgba(245,158,11,0.05)", "icon": "📱",
            "action": "Send a check-in message",
            "detail": "Low VLE activity is the strongest early predictor of withdrawal. "
                      "A brief, warm check-in (not a warning) significantly improves re-engagement."
        })
    if not instructor_actions:
        instructor_actions.append({
            "color":  "#10b981", "bg": "rgba(16,185,129,0.07)", "icon": "✅",
            "action": "No urgent action needed",
            "detail": "This student is on track. A positive acknowledgement note can help maintain motivation."
        })

    for act in instructor_actions:
        st.markdown(f"""
        <div class="action-card" style="background:{act['bg']};border-left-color:{act['color']}">
            <div style="font-weight:600;color:{act['color']};margin-bottom:5px">
                {act['icon']} {act['action']}</div>
            <div style="font-size:0.87rem;color:#94a3b8">{act['detail']}</div>
        </div>""", unsafe_allow_html=True)

    # ── Email template ────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📧 Generate a support message for this student"):
        msg_type = st.radio("Message type",
            ["Urgent outreach", "Gentle check-in", "Positive encouragement"], horizontal=True)

        templates = {
            "Urgent outreach": f"""Dear Student {sel_id},

I'm reaching out because I've noticed your engagement with {module} has been lower than expected lately. I want to make sure everything is okay and see if there's anything I can do to help.

Your current progress shows some areas of concern, and I'd really like to speak with you before things get harder to turn around. Would you be available for a brief call or meeting this week?

Please don't hesitate to reach out — we're here to support you.

Best regards,
[Your name]""",
            "Gentle check-in": f"""Hi Student {sel_id},

Just checking in to see how you're finding {module} so far. I noticed your activity has been a bit lower recently — completely understandable, but I wanted to make sure you're aware of the support available.

If you're finding any topics challenging or need guidance, please feel free to reach out or visit office hours.

Best,
[Your name]""",
            "Positive encouragement": f"""Hi Student {sel_id},

I just wanted to drop a quick note to say you're doing really well in {module}! Your consistent engagement is paying off.

Keep it up — you're on track for a great result.

[Your name]"""
        }
        st.text_area("Message (edit before sending)", value=templates[msg_type], height=200)
        st.download_button("📋 Download message", data=templates[msg_type],
                           file_name=f"message_student_{sel_id}.txt")

# ─────────────────────────────────────────────────────────────────────────────
# CLASS-LEVEL INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">💡 What Your Class Needs Right Now</div>', unsafe_allow_html=True)

if not cohort_table.empty:
    n_urgent = int((cohort_table["status"]=="🔴 Urgent").sum())
    n_watch  = int((cohort_table["status"]=="🟡 Watch").sum())
    avg_late = float(cohort_table["late_count"].mean())
    low_eng  = int((cohort_table["activity_ratio"] < 0.4).sum())

    class_actions = []
    if n_urgent > len(cohort_table) * 0.15:
        class_actions.append(("🚨", "#ef4444",
            f"{n_urgent} students need urgent contact",
            "More than 15% of your class is at serious risk. Consider targeted outreach to the most disengaged students."))
    if avg_late > 1.5:
        class_actions.append(("⏰", "#f59e0b",
            "Late submission rate is high across the class",
            f"Average {avg_late:.1f} late submissions per student. A class-wide deadline reminder could help."))
    if low_eng > len(cohort_table) * 0.3:
        class_actions.append(("📉", "#f59e0b",
            f"{low_eng} students have very low platform engagement",
            "Over 30% of your class is barely using the VLE — a strong predictor of poor outcomes."))
    if not class_actions:
        class_actions.append(("✅", "#10b981",
            "Your class looks healthy overall",
            "Engagement and scores are within normal ranges. Keep monitoring the Watch list."))

    col1, col2 = st.columns(2)
    for i, (icon, color, title, detail) in enumerate(class_actions):
        col = col1 if i % 2 == 0 else col2
        with col:
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
            border-radius:12px;padding:16px;margin-bottom:10px'>
                <div style='font-weight:600;color:{color};margin-bottom:6px'>{icon} {title}</div>
                <div style='font-size:0.87rem;color:#94a3b8'>{detail}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        export_cols = ["id_student","status","avg_score","active_weeks","late_count","health","final_result"]
        at_risk_export = cohort_table[cohort_table["status"]!="🟢 On Track"][export_cols].copy()
        at_risk_export.columns = ["Student ID","Status","Avg Score","Active Weeks","Late Subs","Health","Outcome"]
        st.download_button("📥 Download At-Risk Student List (.csv)",
                           data=at_risk_export.to_csv(index=False),
                           file_name=f"at_risk_{module}_{pres}.csv", mime="text/csv")
    with col_exp2:
        full_export = cohort_table[export_cols].copy()
        full_export.columns = ["Student ID","Status","Avg Score","Active Weeks","Late Subs","Health","Outcome"]
        st.download_button("📥 Download Full Class Report (.csv)",
                           data=full_export.to_csv(index=False),
                           file_name=f"full_class_{module}_{pres}.csv", mime="text/csv")
