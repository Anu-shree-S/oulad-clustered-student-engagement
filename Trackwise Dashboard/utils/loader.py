import pandas as pd
import streamlit as st
from pathlib import Path

DATA = Path("data")

@st.cache_data
def load_student_info():
    return pd.read_csv(DATA / "studentInfo.csv")

@st.cache_data
def load_vle():
    df = pd.read_csv(DATA / "studentVle.csv")
    df["date"] = pd.to_numeric(df["date"], errors="coerce")
    df["sum_click"] = pd.to_numeric(df["sum_click"], errors="coerce").fillna(0).clip(lower=0)
    return df

@st.cache_data
def load_assessments():
    sa = pd.read_csv(DATA / "studentAssessment.csv")
    a  = pd.read_csv(DATA / "assessments.csv")
    return sa.merge(a, on="id_assessment", how="left")

@st.cache_data
def load_vle_with_types():
    vle_clicks = pd.read_csv(DATA / "studentVle.csv")
    vle_info   = pd.read_csv(DATA / "vle.csv")
    vle_clicks["date"] = pd.to_numeric(vle_clicks["date"], errors="coerce")
    vle_clicks["sum_click"] = pd.to_numeric(vle_clicks["sum_click"], errors="coerce").fillna(0)
    merged = vle_clicks.merge(vle_info[["id_site","activity_type"]], on="id_site", how="left")
    merged = merged[merged["date"] >= 0].copy()
    merged["week"] = (merged["date"] // 7) + 1

    CONTENT    = {"subpage","homepage","oucontent","resource","url","page",
                  "folder","glossary","htmlactivity","dualpane","repeatactivity"}
    ASSESSMENT = {"quiz","externalquiz","questionnaire"}
    SOCIAL     = {"forumng","ouwiki","oucollaborate","ouelluminate",
                  "dataplus","sharedsubpage"}

    def dim(a):
        if pd.isna(a): return "other"
        a = str(a).lower()
        if a in CONTENT:    return "content"
        if a in ASSESSMENT: return "assessment"
        if a in SOCIAL:     return "social"
        return "other"

    merged["engagement_dim"] = merged["activity_type"].apply(dim)
    return merged

@st.cache_data
def load_courses():
    return pd.read_csv(DATA / "courses.csv")

import joblib

@st.cache_resource   # cache_resource for non-data objects like models
def load_ml_tables():
    tables = {}
    for name in ["master","Q1","Q2","Q3","Q4"]:
        tables[f"{name}_train"] = pd.read_parquet(DATA / f"ml_{name}_train.parquet")
        tables[f"{name}_test"]  = pd.read_parquet(DATA / f"ml_{name}_test.parquet")
    return tables

@st.cache_resource
def load_cluster_models():
    models = {}
    for name in ["master","Q1","Q2","Q3","Q4"]:
        models[name] = {
            "model":  joblib.load(DATA / f"models/kmeans_{name}.pkl"),
            "scaler": joblib.load(DATA / f"models/scaler_{name}.pkl"),
        }
    return models
