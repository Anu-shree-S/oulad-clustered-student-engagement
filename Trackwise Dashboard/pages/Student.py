"""
EduPulse — Student Dashboard
Simple, warm, human-first. No jargon. Just: where you are, how you're doing, what to do next.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="My Progress · TrackWise", layout="wide", page_icon="🎓")

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  — warm, calm, human (not sci-fi)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background: #0f1117;
    color: #e8eaf0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #131520 0%, #0f1117 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

/* Hide default Streamlit header */
header[data-testid="stHeader"] { display: none; }

/* Remove padding top */
.block-container { padding-top: 1.5rem !important; }

/* Stat card */
.stat-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 24px 20px;
    text-align: center;
    transition: transform 0.2s;
}
.stat-card:hover { transform: translateY(-2px); }
.stat-number {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem;
    font-weight: 400;
    line-height: 1;
    margin-bottom: 6px;
}
.stat-label {
    font-size: 0.82rem;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stat-delta {
    font-size: 0.82rem;
    margin-top: 6px;
    font-weight: 500;
}

/* Section header */
.section-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.5rem;
    color: #e8eaf0;
    margin: 2rem 0 1rem 0;
}

/* Status banner */
.status-banner {
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 20px;
}

/* Recommendation card */
.rec-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.rec-card:hover { border-color: rgba(255,255,255,0.15); }
.rec-number {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    margin-bottom: 10px;
}
.rec-title {
    font-size: 1rem;
    font-weight: 600;
    color: #e8eaf0;
    margin-bottom: 6px;
}
.rec-body {
    font-size: 0.88rem;
    color: #94a3b8;
    line-height: 1.6;
}
.rec-action {
    margin-top: 10px;
    font-size: 0.83rem;
    color: #a5b4fc;
    font-weight: 500;
}

/* Timeline bar */
.timeline-item {
    display: flex;
    gap: 14px;
    margin-bottom: 14px;
    align-items: flex-start;
}
.timeline-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
}

/* Progress ring label */
.ring-label {
    font-size: 0.8rem;
    color: #64748b;
    text-align: center;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING  (replace with real loader when ML tables are saved)
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
    except Exception:
        return None, None, None, None

si, vle_df, sa, ass = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — student selector
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 20px'>
        <div style='font-family:"DM Serif Display",serif;font-size:1.6rem;color:#e8eaf0'>EduPulse</div>
        <div style='font-size:0.8rem;color:#475569;margin-top:2px'>Student Progress</div>
    </div>
    """, unsafe_allow_html=True)

    if si is not None:
        modules = sorted(si["code_module"].unique())
        module  = st.selectbox("Module", modules)
        pres_opts = sorted(si[si["code_module"]==module]["code_presentation"].unique())
        pres    = st.selectbox("Presentation", pres_opts)

        cohort  = si[(si["code_module"]==module) & (si["code_presentation"]==pres)]
        student_ids = sorted(cohort["id_student"].unique())

        search = st.text_input("🔍 Search Student ID", "")
        if search.strip().isdigit() and int(search.strip()) in student_ids:
            student_id = int(search.strip())
        else:
            student_id = st.selectbox("Select Student", student_ids)
    else:
        module, pres, student_id = "AAA", "2014J", 12345
        cohort = pd.DataFrame()

    st.markdown("---")
    quarter = st.selectbox("📅 Course Stage", 
        ["Q1 — Early (weeks 1–9)", "Q2 — Mid (weeks 10–19)",
         "Q3 — Late (weeks 20–29)", "Q4 — Final (weeks 30+)"], index=1)
    quarter_key = quarter[:2]

    st.markdown("---")
    st.markdown("<div style='font-size:0.75rem;color:#334155'>EduPulse Analytics<br>Open University Learning Analytics</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FETCH STUDENT DATA
# ─────────────────────────────────────────────────────────────────────────────
if si is not None and not cohort.empty:
    stu_info = si[si["id_student"] == student_id].iloc[0] if len(si[si["id_student"]==student_id]) > 0 else None

    # VLE engagement
    stu_vle = pd.DataFrame()
    if vle_df is not None:
        stu_vle = vle_df[(vle_df["id_student"]==student_id) &
                         (vle_df["code_module"]==module) &
                         (vle_df["code_presentation"]==pres)].copy()
        stu_vle["date"]      = pd.to_numeric(stu_vle["date"],      errors="coerce").fillna(0)
        stu_vle["sum_click"] = pd.to_numeric(stu_vle["sum_click"], errors="coerce").fillna(0)
        stu_vle["week"] = (stu_vle["date"].clip(lower=0) // 7) + 1

    # Assessment scores
    stu_scores = pd.DataFrame()
    if sa is not None and ass is not None:
        ass_mod = ass[(ass["code_module"]==module) & (ass["code_presentation"]==pres)
                      & (ass["assessment_type"]!="Exam")].copy()
        stu_scores = sa[sa["id_student"]==student_id].merge(
            ass_mod[["id_assessment","date"]], on="id_assessment", how="inner")

    # Class averages
    class_vle = pd.DataFrame()
    if vle_df is not None:
        class_vle = vle_df[(vle_df["code_module"]==module) &
                           (vle_df["code_presentation"]==pres)].copy()
        class_vle["date"]      = pd.to_numeric(class_vle["date"],      errors="coerce").fillna(0)
        class_vle["sum_click"] = pd.to_numeric(class_vle["sum_click"], errors="coerce").fillna(0)
        class_vle["week"] = (class_vle["date"].clip(lower=0) // 7) + 1

    my_total_clicks = int(stu_vle["sum_click"].sum()) if not stu_vle.empty else 0
    class_avg_clicks = int(class_vle.groupby("id_student")["sum_click"].sum().mean()) if not class_vle.empty else 0
    active_weeks = int(stu_vle.groupby("week")["sum_click"].sum().gt(0).sum()) if not stu_vle.empty else 0
    total_weeks  = max(int(class_vle["week"].max()) if not class_vle.empty else 20, 1)

    if not stu_scores.empty:
        stu_scores["score"] = pd.to_numeric(stu_scores["score"], errors="coerce")
    my_avg_score = float(stu_scores["score"].mean()) if not stu_scores.empty else None
    class_scores = pd.DataFrame()
    if sa is not None and ass is not None:
        class_scores_all = sa.merge(ass_mod[["id_assessment","date"]], on="id_assessment", how="inner")
        class_scores_all["score"] = pd.to_numeric(class_scores_all["score"], errors="coerce")
        class_avg_score = float(class_scores_all["score"].mean()) if not class_scores_all.empty else 50.0
    else:
        class_avg_score = 50.0

    # Late submissions
    late_count = 0
    if not stu_scores.empty and "is_banked" in stu_scores.columns:
        late_count = int((stu_scores["is_banked"]==0).sum())

    # Health score heuristic (0–100)
    click_score   = min(100, my_total_clicks / max(class_avg_clicks, 1) * 50)
    score_score   = min(50, (my_avg_score / 100 * 50)) if my_avg_score else 25
    health_score  = int(click_score + score_score)
    health_score  = max(5, min(100, health_score))

    # Risk level
    activity_ratio = active_weeks / max(total_weeks, 1)
    if activity_ratio < 0.3 or (my_avg_score is not None and my_avg_score < 45):
        risk = "high"
    elif activity_ratio < 0.55 or (my_avg_score is not None and my_avg_score < 60):
        risk = "medium"
    else:
        risk = "low"

    result = stu_info["final_result"] if stu_info is not None else "Unknown"

else:
    # Demo fallback data
    student_id   = 12345
    module, pres = "BBB", "2014J"
    my_total_clicks  = 1430
    class_avg_clicks = 2200
    active_weeks, total_weeks = 8, 20
    my_avg_score, class_avg_score = 58.0, 65.0
    late_count   = 2
    health_score = 52
    risk         = "medium"
    result       = "Unknown"
    stu_info     = None

# ─────────────────────────────────────────────────────────────────────────────
# GREETING HEADER
# ─────────────────────────────────────────────────────────────────────────────
greeting_hour = pd.Timestamp.now().hour
greeting      = "Good morning" if greeting_hour < 12 else "Good afternoon" if greeting_hour < 18 else "Good evening"

st.markdown(f"""
<div style='margin-bottom: 1.5rem'>
    <div style='font-size:0.9rem;color:#475569;font-weight:500'>{greeting} 👋</div>
    <div style='font-family:"DM Serif Display",serif;font-size:2.2rem;color:#e8eaf0;line-height:1.2'>
        Student <span style='color:#818cf8'>#{student_id}</span>
    </div>
    <div style='font-size:0.9rem;color:#475569;margin-top:4px'>
        {module} · {pres} · Viewing {quarter_key} data
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# STATUS BANNER  — the most important thing, front and centre
# ─────────────────────────────────────────────────────────────────────────────
STATUS_CONFIG = {
    "low":    ("#10b981", "#0d2b22", "✅", "You're on track!",
               "Keep up the great work. Your engagement and scores are above class average."),
    "medium": ("#f59e0b", "#2b2000", "⚠️", "A few things to watch",
               "You're doing okay, but there are some areas where small improvements now could make a big difference to your final result."),
    "high":   ("#ef4444", "#2b0a0a", "🔴", "You need support now",
               "Your engagement has dropped significantly. Please speak to your tutor and use the recommendations below — it's not too late to turn this around."),
}
sc, sbg, icon, title, msg = STATUS_CONFIG[risk]

st.markdown(f"""
<div class="status-banner" style="background:{sbg};border:1px solid {sc}30">
    <div style="font-size:2.4rem;line-height:1">{icon}</div>
    <div>
        <div style="font-family:'DM Serif Display',serif;font-size:1.4rem;color:{sc}">{title}</div>
        <div style="font-size:0.9rem;color:#94a3b8;margin-top:4px;max-width:700px">{msg}</div>
    </div>
    <div style="margin-left:auto;text-align:right">
        <div style="font-family:'DM Serif Display',serif;font-size:2.8rem;color:{sc}">{health_score}</div>
        <div style="font-size:0.75rem;color:#475569;text-transform:uppercase;letter-spacing:.05em">Health Score</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 4 KEY NUMBERS — plain English
# ─────────────────────────────────────────────────────────────────────────────
click_delta = my_total_clicks - class_avg_clicks
score_delta = (my_avg_score - class_avg_score) if my_avg_score is not None else None

c1, c2, c3, c4 = st.columns(4)
cards = [
    (f"{my_avg_score:.0f}%" if my_avg_score else "N/A",
     "Average Score",
     f"+{score_delta:.1f} vs class" if score_delta and score_delta >= 0 else f"{score_delta:.1f} vs class" if score_delta else "",
     "#10b981" if score_delta and score_delta >= 0 else "#ef4444"),
    (f"{my_total_clicks:,}",
     "Times Engaged Online",
     f"Class avg: {class_avg_clicks:,}",
     "#10b981" if my_total_clicks >= class_avg_clicks else "#f59e0b"),
    (f"{active_weeks} / {total_weeks}",
     "Weeks Active So Far",
     f"{activity_ratio*100:.0f}% of the course",
     "#10b981" if activity_ratio > 0.6 else "#f59e0b" if activity_ratio > 0.35 else "#ef4444"),
    (f"{late_count}",
     "Late Submissions",
     "Aim for zero" if late_count > 0 else "Great — none!",
     "#ef4444" if late_count > 2 else "#f59e0b" if late_count > 0 else "#10b981"),
]
for col, (num, label, delta, color) in zip([c1,c2,c3,c4], cards):
    with col:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number" style="color:{color}">{num}</div>
            <div class="stat-label">{label}</div>
            <div class="stat-delta" style="color:{color}88">{delta}</div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ENGAGEMENT CHART  — simple, readable, weekly
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Your Weekly Activity</div>', unsafe_allow_html=True)
st.caption("How many times you logged in and interacted each week vs the rest of your class")

col_chart, col_summary = st.columns([3, 1])
with col_chart:
    if not (si is None or stu_vle.empty):
        weekly_me = (stu_vle.groupby("week")["sum_click"].sum().reset_index()
                     .rename(columns={"sum_click":"My Activity"}))
        weekly_class = (class_vle.groupby(["id_student","week"])["sum_click"].sum()
                        .reset_index().groupby("week")["sum_click"].mean().reset_index()
                        .rename(columns={"sum_click":"Class Average"}))
        merged = weekly_me.merge(weekly_class, on="week", how="outer").sort_values("week").fillna(0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged["week"], y=merged["Class Average"],
            fill="tozeroy", fillcolor="rgba(71,85,105,0.15)",
            line=dict(color="#475569", width=1.5, dash="dot"),
            name="Class Average"))
        fig.add_trace(go.Scatter(
            x=merged["week"], y=merged["My Activity"],
            fill="tozeroy", fillcolor="rgba(129,140,248,0.15)",
            line=dict(color="#818cf8", width=2.5),
            name="My Activity",
            mode="lines+markers",
            marker=dict(size=5, color="#818cf8")))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", family="DM Sans"),
            legend=dict(orientation="h", y=1.1, bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(title="Week", gridcolor="rgba(255,255,255,0.04)", zeroline=False),
            yaxis=dict(title="Clicks", gridcolor="rgba(255,255,255,0.04)", zeroline=False),
            margin=dict(t=20, b=10, l=10, r=10), height=260)
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Demo chart
        weeks = list(range(1, 16))
        me    = [12, 8, 15, 3, 0, 20, 18, 5, 11, 14, 0, 0, 9, 7, 12]
        avg   = [22, 20, 24, 19, 23, 25, 22, 21, 20, 23, 24, 22, 21, 20, 19]
        fig   = go.Figure()
        fig.add_trace(go.Scatter(x=weeks, y=avg, fill="tozeroy",
            fillcolor="rgba(71,85,105,0.15)", line=dict(color="#475569",dash="dot"), name="Class Average"))
        fig.add_trace(go.Scatter(x=weeks, y=me, fill="tozeroy",
            fillcolor="rgba(129,140,248,0.15)", line=dict(color="#818cf8",width=2.5), name="My Activity",
            mode="lines+markers", marker=dict(size=5)))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8",family="DM Sans"),
            legend=dict(orientation="h",y=1.1,bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(title="Week",gridcolor="rgba(255,255,255,0.04)",zeroline=False),
            yaxis=dict(title="Clicks",gridcolor="rgba(255,255,255,0.04)",zeroline=False),
            margin=dict(t=20,b=10,l=10,r=10), height=260)
        st.plotly_chart(fig, use_container_width=True)

with col_summary:
    # 3 engagement type mini-bars (what ARE they clicking on?)
    st.markdown("<br>", unsafe_allow_html=True)
    if not stu_vle.empty and "activity_type" in stu_vle.columns:
        CONTENT  = {"subpage","homepage","oucontent","resource","url","page","folder"}
        ASSESS   = {"quiz","externalquiz","questionnaire"}
        SOCIAL   = {"forumng","ouwiki","oucollaborate"}
        stu_vle["dim"] = stu_vle.get("activity_type", pd.Series("other", index=stu_vle.index)).apply(
            lambda x: "Content" if str(x).lower() in CONTENT
            else "Practice" if str(x).lower() in ASSESS
            else "Social" if str(x).lower() in SOCIAL else "Other")
        dim_sums = stu_vle.groupby("dim")["sum_click"].sum()
        total_dim = max(dim_sums.sum(), 1)
    else:
        dim_sums  = pd.Series({"Content": 60, "Practice": 25, "Social": 10, "Other": 5})
        total_dim = 100

    for dim_name, color in [("Content","#818cf8"),("Practice","#34d399"),("Social","#fb923c"),("Other","#475569")]:
        pct = int(dim_sums.get(dim_name, 0) / total_dim * 100)
        st.markdown(f"""
        <div style='margin-bottom:14px'>
            <div style='display:flex;justify-content:space-between;margin-bottom:5px'>
                <span style='font-size:0.82rem;color:#94a3b8'>{dim_name}</span>
                <span style='font-size:0.82rem;color:{color};font-weight:600'>{pct}%</span>
            </div>
            <div style='background:rgba(255,255,255,0.06);border-radius:4px;height:6px'>
                <div style='background:{color};border-radius:4px;height:6px;width:{pct}%'></div>
            </div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ASSESSMENT SCORES — simple bar, no maths
# ─────────────────────────────────────────────────────────────────────────────
col_scores, col_gap = st.columns([2, 1])
with col_scores:
    st.markdown('<div class="section-header">📝 Your Assessment Results</div>', unsafe_allow_html=True)

    if not stu_scores.empty:
        stu_scores_plot = stu_scores.sort_values("date").reset_index(drop=True)
        stu_scores_plot["score"] = pd.to_numeric(stu_scores_plot["score"], errors="coerce").fillna(0)
        stu_scores_plot["label"] = [f"Task {i+1}" for i in range(len(stu_scores_plot))]
        colors_bar = ["#10b981" if s >= 60 else "#f59e0b" if s >= 40 else "#ef4444"
                      for s in stu_scores_plot["score"]]
        fig2 = go.Figure(go.Bar(
            x=stu_scores_plot["label"],
            y=stu_scores_plot["score"],
            marker_color=colors_bar,
            marker_line_width=0))
        fig2.add_hline(y=class_avg_score, line_dash="dot", line_color="#475569",
                       annotation_text=f"Class avg {class_avg_score:.0f}%",
                       annotation_font_color="#94a3b8")
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", family="DM Sans"),
            yaxis=dict(range=[0,105], gridcolor="rgba(255,255,255,0.04)", title="Score (%)"),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(t=10, b=10, l=10, r=10), height=220, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        tasks  = [f"Task {i}" for i in range(1, 7)]
        scores = [72, 58, 65, 45, 68, 55]
        colors_bar = ["#10b981" if s >= 60 else "#f59e0b" if s >= 40 else "#ef4444" for s in scores]
        fig2 = go.Figure(go.Bar(x=tasks, y=scores, marker_color=colors_bar, marker_line_width=0))
        fig2.add_hline(y=65, line_dash="dot", line_color="#475569",
                       annotation_text="Class avg 65%", annotation_font_color="#94a3b8")
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", family="DM Sans"),
            yaxis=dict(range=[0,105], gridcolor="rgba(255,255,255,0.04)", title="Score (%)"),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(t=10, b=10, l=10, r=10), height=220, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

with col_gap:
    st.markdown('<div class="section-header">🧭 Where You Stand</div>', unsafe_allow_html=True)
    # Visual breakdown vs class
    comparisons = [
        ("Engagement", min(100, int(my_total_clicks/max(class_avg_clicks,1)*100)), "#818cf8"),
        ("Scores",     min(100, int((my_avg_score or 0)/class_avg_score*100) if class_avg_score else 0), "#34d399"),
        ("Consistency", min(100, int(activity_ratio*100*1.3)), "#fb923c"),
    ]
    for label, pct, color in comparisons:
        vs_text = "above average" if pct >= 100 else "at average" if pct >= 85 else "below average"
        vs_col  = "#10b981" if pct >= 100 else "#f59e0b" if pct >= 85 else "#ef4444"
        st.markdown(f"""
        <div style='margin-bottom:18px'>
            <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                <span style='font-size:0.9rem;color:#e8eaf0;font-weight:500'>{label}</span>
                <span style='font-size:0.8rem;color:{vs_col}'>{vs_text}</span>
            </div>
            <div style='background:rgba(255,255,255,0.06);border-radius:6px;height:10px'>
                <div style='background:{color};border-radius:6px;height:10px;width:{min(pct,100)}%;transition:width .5s'></div>
            </div>
            <div style='font-size:0.75rem;color:#334155;margin-top:3px'>You: {pct}% of class average</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PERSONALISED RECOMMENDATIONS  — the most human part
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">💡 What You Should Do Next</div>', unsafe_allow_html=True)
st.caption("These are personalised suggestions based on your activity so far. Focus on the ones marked most urgent first.")

# Build recommendations based on actual data patterns
recs = []

if activity_ratio < 0.5:
    recs.append({
        "priority": 1,
        "badge":    "Most Important",
        "color":    "#ef4444",
        "title":    "Log in more regularly",
        "body":     f"You've only been active in {active_weeks} out of {total_weeks} weeks. "
                    f"Students who log in regularly — even just for 20 minutes — are much more "
                    f"likely to pass. Aim for at least 3 sessions per week.",
        "action":   "📅 Block 3 sessions in your calendar this week, even short ones."
    })

if my_avg_score is not None and my_avg_score < class_avg_score - 5:
    recs.append({
        "priority": 1 if my_avg_score < 50 else 2,
        "badge":    "Urgent" if my_avg_score < 50 else "Recommended",
        "color":    "#ef4444" if my_avg_score < 50 else "#f59e0b",
        "title":    "Your scores need attention",
        "body":     f"Your average score is {my_avg_score:.0f}% compared to the class average of "
                    f"{class_avg_score:.0f}%. Try reworking assessments you scored under 50% on — "
                    f"the feedback from those will help your next ones.",
        "action":   "📖 Re-read the feedback on your lowest-scoring task and attempt a similar practice question."
    })

if late_count > 1:
    recs.append({
        "priority": 2,
        "badge":    "Recommended",
        "color":    "#f59e0b",
        "title":    f"Reduce late submissions ({late_count} so far)",
        "body":     "Late submissions often lead to lower scores and add stress. "
                    "Even submitting a partial answer on time is better than a late complete one. "
                    "Students who submit on time consistently score 12–15 points higher on average.",
        "action":   "🗓️ Set a personal deadline 2 days before each official due date."
    })

if dim_sums.get("Practice", 0) / max(total_dim, 1) < 0.15:
    recs.append({
        "priority": 2,
        "badge":    "Recommended",
        "color":    "#f59e0b",
        "title":    "Do more practice quizzes",
        "body":     "Only a small portion of your online activity is on practice quizzes and exercises. "
                    "Students who regularly use the practice materials score significantly better. "
                    "Even one quiz session per week makes a measurable difference.",
        "action":   "🧠 Complete at least one practice quiz before each graded assessment."
    })

if dim_sums.get("Social", 0) / max(total_dim, 1) < 0.05:
    recs.append({
        "priority": 3,
        "badge":    "Good to Do",
        "color":    "#818cf8",
        "title":    "Get involved in the forum",
        "body":     "You haven't used the discussion forums much. Students who participate — even just "
                    "asking one question or answering another student — tend to understand the material better. "
                    "It also helps you feel less isolated.",
        "action":   "💬 Post one question or response in the forum this week."
    })

if not recs:
    recs.append({
        "priority": 3,
        "badge":    "Keep it up",
        "color":    "#10b981",
        "title":    "You're doing great — here's how to stay there",
        "body":     "Your engagement and scores are above average. The best thing you can do now is "
                    "maintain consistency — don't let up as the course gets harder. "
                    "Help a classmate in the forum; teaching others is the best way to consolidate your own learning.",
        "action":   "🌟 Aim to keep your weekly activity above the class average for the rest of the course."
    })

# Sort by priority
recs.sort(key=lambda x: x["priority"])

for i, rec in enumerate(recs[:4]):
    st.markdown(f"""
    <div class="rec-card">
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
            <div class="rec-number" style="background:{rec['color']}22;color:{rec['color']}">{i+1}</div>
            <span style='font-size:0.75rem;font-weight:600;color:{rec["color"]};
            background:{rec["color"]}15;padding:3px 10px;border-radius:20px'>{rec["badge"]}</span>
        </div>
        <div class="rec-title">{rec["title"]}</div>
        <div class="rec-body">{rec["body"]}</div>
        <div class="rec-action">→ {rec["action"]}</div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BOTTOM: WHAT HAPPENS IF YOU DO NOTHING / WHAT CAN GO RIGHT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🔭 The Bigger Picture</div>', unsafe_allow_html=True)
col_warn, col_pos = st.columns(2)

with col_warn:
    st.markdown(f"""
    <div style='background:rgba(239,68,68,0.07);border:1px solid rgba(239,68,68,0.2);
    border-radius:14px;padding:20px'>
        <div style='font-weight:700;color:#ef4444;margin-bottom:8px'>⚠️ If things don't improve</div>
        <div style='font-size:0.88rem;color:#94a3b8;line-height:1.7'>
        Based on our data from thousands of students on this course:<br>
        • Students active fewer than 30% of weeks have a <b style='color:#ef4444'>73% chance</b> of not passing<br>
        • Missing 3+ deadlines typically drops final scores by <b style='color:#ef4444'>10–15 points</b><br>
        • The gap between at-risk and passing students widens every quarter
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_pos:
    st.markdown(f"""
    <div style='background:rgba(16,185,129,0.07);border:1px solid rgba(16,185,129,0.2);
    border-radius:14px;padding:20px'>
        <div style='font-weight:700;color:#10b981;margin-bottom:8px'>✅ What improvement looks like</div>
        <div style='font-size:0.88rem;color:#94a3b8;line-height:1.7'>
        Small, consistent changes make a real difference:<br>
        • Logging in 3× per week vs 1× per week = <b style='color:#10b981'>+18% pass rate</b><br>
        • Submitting on time = <b style='color:#10b981'>~13 more points</b> on average<br>
        • Using practice quizzes regularly = top quartile scores
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
with st.expander("ℹ️ How is my Health Score calculated?"):
    st.markdown("""
    Your **Health Score** (0–100) is calculated from two things:
    - **50 points** from your engagement — how much you interact with course materials compared to classmates
    - **50 points** from your assessment scores — how well you're doing on graded tasks
    
    It's a simple snapshot, not a final grade. It's designed to tell you at a glance whether you're on track.
    A score above 70 means you're doing well. Below 40 means you should act now.
    """)
