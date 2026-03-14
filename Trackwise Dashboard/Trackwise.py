import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="TrackWise Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main { background: #0a0a1a; }

/* Glassmorphism card */
.glass-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 20px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.glass-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(99,102,241,0.3);
}

/* Hero gradient text */
.hero-title {
    font-size: 3.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #06b6d4, #10b981);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.1;
    margin-bottom: 8px;
}
.hero-sub {
    font-size: 1.2rem;
    color: #94a3b8;
    margin-bottom: 32px;
}

/* Role cards */
.role-card {
    background: rgba(255,255,255,0.04);
    border-radius: 20px;
    padding: 32px 24px;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.3s ease;
    height: 100%;
}
.role-card:hover {
    background: rgba(99,102,241,0.15);
    border-color: rgba(99,102,241,0.5);
    transform: translateY(-6px);
}
.role-icon { font-size: 3rem; margin-bottom: 12px; }
.role-title { font-size: 1.4rem; font-weight: 700; color: #e2e8f0; }
.role-desc  { font-size: 0.9rem; color: #94a3b8; margin-top: 8px; line-height: 1.5; }

/* Feature pills */
.feature-pill {
    display: inline-block;
    background: rgba(99,102,241,0.2);
    border: 1px solid rgba(99,102,241,0.4);
    color: #a5b4fc;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.8rem;
    margin: 3px;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(6,182,212,0.1));
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
}
.metric-value { font-size: 2rem; font-weight: 800; color: #e2e8f0; }
.metric-label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
    border-right: 1px solid rgba(99,102,241,0.2);
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 24px;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

/* Divider */
.gradient-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, #6366f1, #06b6d4, transparent);
    border: none;
    margin: 24px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Hero Section ──────────────────────────────────────────────────────────────
col_hero, col_badge = st.columns([3,1])
with col_hero:
    st.markdown('<div class="hero-title">TrackWise Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">AI-powered learning analytics platform for modern educational institutions</div>', unsafe_allow_html=True)

with col_badge:
    st.markdown("""
    <div style='text-align:right; padding-top:20px'>
        <span class="feature-pill">🤖 ML-Powered</span>
        <span class="feature-pill">📊 Real-time</span><br>
        <span class="feature-pill">🔒 Role-Based</span>
        <span class="feature-pill">📥 Exportable</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="gradient-divider">', unsafe_allow_html=True)

# ── Data Upload Section ───────────────────────────────────────────────────────
st.markdown("### 📂 Data Source")
data_mode = st.radio(
    "Choose how to load data:",
    ["🎓 Use built-in OULAD dataset", "📤 Upload my institution's data"],
    horizontal=True
)

if data_mode == "📤 Upload my institution's data":
    st.markdown("""
    <div class="glass-card">
    <h4 style='color:#a5b4fc'>📋 Required CSV Format</h4>
    <p style='color:#94a3b8'>Upload a student info CSV with these columns:</p>
    <code style='color:#06b6d4'>id_student, code_module, code_presentation, gender, age_band,
    highest_education, imd_band, region, disability, final_result, studied_credits, num_of_prev_attempts</code>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload studentInfo CSV", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.success(f"✅ Loaded {len(df):,} students from your dataset!")
        st.session_state["custom_data"] = df
        st.dataframe(df.head(5), use_container_width=True)
    else:
        st.info("👆 Upload your CSV above to get started with your institution's data.")
else:
    if "custom_data" in st.session_state:
        del st.session_state["custom_data"]
    st.success("✅ Using built-in OULAD dataset — 32,593 students across 7 modules")

st.markdown('<hr class="gradient-divider">', unsafe_allow_html=True)

# ── Role Cards ────────────────────────────────────────────────────────────────
st.markdown("### 👤 Select Your Role")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="role-card">
        <div class="role-icon">🎓</div>
        <div class="role-title" style="color:#a5b4fc">Student</div>
        <div class="role-desc">Personal risk score, progress tracking,
        engagement vs peers, and AI-powered study recommendations</div>
        <br>
        <span class="feature-pill">Risk Gauge</span>
        <span class="feature-pill">Score Trends</span>
        <span class="feature-pill">Recommendations</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="role-card">
        <div class="role-icon">📋</div>
        <div class="role-title" style="color:#34d399">Instructor</div>
        <div class="role-desc">Class-wide at-risk alerts, engagement trends,
        individual student drill-down and exportable reports</div>
        <br>
        <span class="feature-pill">At-Risk Alerts</span>
        <span class="feature-pill">Drill-Down</span>
        <span class="feature-pill">Export Excel</span>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="role-card">
        <div class="role-icon">🏛️</div>
        <div class="role-title" style="color:#f87171">Administrator</div>
        <div class="role-desc">Institution-wide KPIs, module comparisons,
        demographic analysis and strategic insights</div>
        <br>
        <span class="feature-pill">KPI Overview</span>
        <span class="feature-pill">Demographics</span>
        <span class="feature-pill">Export PDF</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
role = st.selectbox(
    "Select your role to enter dashboard:",
    ["— Select a role —", "🎓 Student", "📋 Instructor", "🏛️ Administrator"]
)

if role == "🎓 Student":
    st.success("✅ Click **1 Student** in the sidebar →")
    st.page_link("pages/1_Student.py", label="→ Enter Student Dashboard", icon="🎓")
elif role == "📋 Instructor":
    st.success("✅ Click **2 Instructor** in the sidebar →")
    st.page_link("pages/2_Instructor.py", label="→ Enter Instructor Dashboard", icon="📋")
elif role == "🏛️ Administrator":
    st.success("✅ Click **3 Admin** in the sidebar →")
    st.page_link("pages/3_Admin.py", label="→ Enter Admin Dashboard", icon="🏛️")

st.markdown('<hr class="gradient-divider">', unsafe_allow_html=True)

# ── Platform Stats ─────────────────────────────────────────────────────────────
st.markdown("### 📊 Platform Capability")
c1, c2, c3, c4, c5 = st.columns(5)
stats = [
    ("32,593+", "Students Analysed"),
    ("7", "Course Modules"),
    ("3", "User Roles"),
    ("ML", "Risk Prediction"),
    ("100%", "Customisable"),
]
for col, (val, label) in zip([c1,c2,c3,c4,c5], stats):
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{val}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)
