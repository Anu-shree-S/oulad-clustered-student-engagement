# oulad-clustered-student-engagement
OULAD-based project that clusters students using early engagement behaviour to analyse academic outcomes and explore early intervention strategies in online learning.
# Behavioural Learning Analytics for Early Student Support

GitHub Repository:  
https://github.com/Anu-shree-S/oulad-clustered-student-engagement

The project uses the **Open University Learning Analytics Dataset (OULAD)** to model student behavioural engagement, identify students at risk of failing or withdrawing, analyse behavioural learner clusters, and generate targeted intervention recommendations.

The project should be executed in the following order:

**1. Clone the repository**  
**2. Add the OULAD raw data**  
**3. Run the final modelling pipeline**  
**4. Run the recommendation pipeline**  
**5. Launch the TrackWise dashboard**

---

# 1. Clone the GitHub Repository

Open Command Prompt, PowerShell, Git Bash, or a terminal and run:

```bash
git clone https://github.com/Anu-shree-S/oulad-clustered-student-engagement.git
```

Move into the repository:

```bash
cd oulad-clustered-student-engagement
```

The relevant project structure is:

```text
oulad-clustered-student-engagement/
│
├── data/
│   └── raw/
│
├── notebooks/
│   ├── eda.ipynb
│   ├── final_pipeline_dashboard_deployment.ipynb
│   └── recommendation-pipeline.ipynb
│
├── oulad_dashboard/
│   ├── app.py
│   ├── pages/
│   ├── services/
│   ├── components/
│   └── data/
│
├── requirements.txt
└── README.md
```

The OULAD dataset itself is **not stored in GitHub** because of its size.

---

# 2. Add the OULAD Dataset

The raw OULAD dataset will be supplied separately.

Extract the supplied dataset and place the original CSV files inside:

```text
oulad-clustered-student-engagement/data/raw/
```

The final structure must therefore be:

```text
data/
└── raw/
    ├── assessments.csv
    ├── courses.csv
    ├── studentAssessment.csv
    ├── studentInfo.csv
    ├── studentRegistration.csv
    ├── studentVle.csv
    └── vle.csv
```

Do **not rename any of the files**.

Both analysis notebooks use the relative data path:

```python
DATA_RAW = Path("../data/raw")
```

For this reason, the notebooks should be executed from the `notebooks/` directory.

---

# 3. Install the Required Python Packages

No virtual environment is required.

From the repository root, install the dashboard dependencies:

```bash
python -m pip install -r oulad_dashboard/requirements.txt
```

Install Jupyter if it is not already available:

```bash
python -m pip install jupyter
```

The modelling notebook also requires the scientific and machine-learning libraries used in the project. Its first cell installs the main modelling dependencies automatically:

```python
%pip install numpy pandas matplotlib seaborn scipy scikit-learn xgboost torch lime shap
```

Therefore, these packages will be installed when the first notebook is executed.

---

# 4. Open the Project Notebooks

Move to the notebook directory:

```bash
cd notebooks
```

Start Jupyter:

```bash
jupyter notebook
```

Open the notebooks from the browser interface.

The notebooks should be executed in this order:

```text
1. final_pipeline_dashboard_deployment.ipynb
2. recommendation-pipeline.ipynb
```

Use:

**Kernel → Restart & Run All**

or execute all cells sequentially from top to bottom.

The second notebook should only be executed **after the first notebook has completed successfully**.

---

# 5. Notebook 1 – Final Modelling Pipeline

File:

```text
notebooks/final_pipeline_dashboard_deployment.ipynb
```

## Purpose

This is the main machine-learning and behavioural analytics pipeline.

It performs the complete workflow from raw OULAD data to student-risk predictions and dashboard-ready prediction outputs.

## Main Processing Performed

The notebook:

- loads and cleans the seven OULAD tables;
- creates the binary risk target:
  - **At Risk = Fail or Withdrawn**
  - **Not At Risk = Pass or Distinction**;
- constructs temporally valid behavioural features;
- calculates course-specific Q1, Q2, Q3 and Q4 checkpoints;
- creates engagement features covering:
  - total engagement;
  - content engagement;
  - assessment engagement;
  - social engagement;
  - active-week behaviour;
  - engagement regularity/entropy;
  - assessment submission behaviour;
  - anti-procrastination behaviour;
  - late submissions;
  - study spacing;
- incorporates demographic and academic-context variables;
- performs behavioural clustering;
- constructs cluster-aware features;
- creates chronological/cross-presentation training and testing datasets;
- trains and evaluates multiple supervised learning approaches;
- compares baseline and cluster-aware models;
- evaluates sequential deep-learning models;
- performs model tuning;
- generates model-performance visualisations;
- performs explainability analysis;
- selects the models used for dashboard deployment;
- generates per-student risk probabilities and predicted risk classes.

## Models Evaluated

The pipeline includes conventional machine-learning models such as:

```text
Logistic Regression
Support Vector Machine
Random Forest
XGBoost
MLP
```

It additionally evaluates sequential models:

```text
LSTM
BiLSTM
Hybrid LSTM
Hybrid BiLSTM
```

and cluster-aware/CAF variants.

## Evaluation

Models are evaluated at progressive semester checkpoints:

```text
Q1
Q2
Q3
Master / full available history
```

using metrics including:

```text
Accuracy
Precision
Recall
F1-score
ROC-AUC
```

The notebook includes comparisons between:

```text
Baseline models
vs.
Cluster-aware models
```

and produces metric tables, ROC-AUC comparisons, confusion matrices, progression plots, heatmaps and model-comparison figures.

## Key Results Produced

The completed experiments show that predictive performance improves as additional behavioural information becomes available.

For example, among the tuned cluster-aware sequential models, **HybridBiLSTM-CAF** produced:

```text
Checkpoint    ROC-AUC
Q1            0.8541
Q2            0.9159
Q3            0.9460
Master        0.9648
```

The Master HybridBiLSTM-CAF result also achieved approximately:

```text
Accuracy   0.9191
Precision  0.9372
Recall     0.8885
F1         0.9122
ROC-AUC    0.9648
```

The analysis also compares these results with simpler baseline, cluster-aware tabular, LSTM/BiLSTM and hybrid approaches.

## Deployment Models

The deployment section uses the already-selected winning model for each operational checkpoint rather than rerunning model selection.

The selected deployment configurations are:

```text
Q1      HybridBiLSTM – cluster-aware/CAF
Q2      HybridBiLSTM – cluster-aware/CAF
Q3      MLP – cluster-aware/CAF
Master  HybridBiLSTM – cluster-aware/CAF
```

There is no separate operational Q4 prediction model; the Master model represents the later/full-history prediction stage.

## Important Outputs

The notebook produces research-result files such as:

```text
results_cv.csv
results_test.csv
results_tuned_baseline.csv
results_tuned_caf.csv
results_hybrid_baseline.csv
results_hybrid_caf_baseline.csv
results_seq_baseline.csv
results_tuned_hybrid_models.csv
results_tuned_hybrid_caf_models.csv
results_tuned_lstm_models.csv
```

Most importantly for the dashboard/recommendation integration, it creates:

```text
oulad_dashboard/data/dashboard_student_predictions.csv
```

and:

```text
oulad_dashboard/data/dashboard_student_quarter.csv
```

These files contain student-level prediction information such as:

```text
risk probability
predicted risk class
prediction threshold
prediction status
model/checkpoint information
```

The `dashboard_student_predictions.csv` file is required by the recommendation notebook.

---

# 6. Notebook 2 – Recommendation Pipeline

File:

```text
notebooks/recommendation-pipeline.ipynb
```

Run this notebook **after** the final modelling pipeline has completed.

## Purpose

The recommendation pipeline converts the behavioural analytics into **interpretable and actionable student-support recommendations**.

The risk model and recommendation system are deliberately separated:

- the **prediction model** estimates whether a student is academically at risk;
- the **recommendation system** determines which observed behaviours could potentially be improved.

The recommendations are therefore behaviour-driven rather than simply being generated because a model predicts that a student is at risk.

## Main Processing Performed

The notebook:

- reconstructs the cleaned behavioural datasets;
- creates Q1–Q4 behavioural feature tables;
- applies the behavioural clustering framework;
- profiles the behavioural clusters;
- identifies successful peer behaviour within appropriate comparison groups;
- compares each learner with relevant successful-peer benchmarks;
- measures behavioural gaps;
- calculates feature relevance and recommendation priority;
- converts technical behavioural features into human-readable support areas;
- generates intervention recommendations;
- creates student-, instructor- and administrator-level dashboard information;
- integrates the previously generated model risk probabilities for contextual display;
- validates recommendation safeguards;
- exports dashboard-ready behavioural and recommendation datasets.

## Recommendation Logic

Recommendations are based on behavioural gaps relative to successful peers.

Examples of behavioural areas include:

```text
Assessment timing
Assessment engagement
Deadline planning
Course-material engagement
Study consistency
Study spacing
Social/peer engagement
```

The system uses behavioural cluster/context information so students are compared against more relevant successful-peer patterns rather than against a single institutional average.

The recommendation layer also:

- suppresses recommendations when a behavioural indicator is undefined;
- avoids recommending corrective action when the learner already meets the relevant benchmark;
- prioritises stronger behavioural gaps;
- avoids repetitive recommendations from the same behavioural category;
- limits the Student dashboard to a small number of high-value recommendations;
- generates interpretable behavioural cluster labels;
- separates behavioural-support status from the predictive-model classification.

Importantly, the student's final academic outcome is **not used to generate live recommendations**. Final outcomes are used only retrospectively for evaluation.

## Recommendation Outputs

For every quarter, the notebook produces a student-level recommendation summary and detailed behavioural gaps.

Final dashboard-facing recommendation files include:

```text
oulad_dashboard/data/recommendations/
│
├── recommendation_summary_Q1.parquet
├── recommendation_summary_Q2.parquet
├── recommendation_summary_Q3.parquet
├── recommendation_summary_Q4.parquet
│
├── recommendation_details_Q1.parquet
├── recommendation_details_Q2.parquet
├── recommendation_details_Q3.parquet
├── recommendation_details_Q4.parquet
│
├── cluster_profiles_Q1.json
├── cluster_profiles_Q2.json
├── cluster_profiles_Q3.json
├── cluster_profiles_Q4.json
│
├── recommendation_quarter_comparison.csv
├── prediction_recommendation_alignment.csv
└── prediction_integration_validation.csv
```

The notebook also exports the behavioural datasets required by the dashboard:

```text
oulad_dashboard/data/ml_Q1_train.parquet
oulad_dashboard/data/ml_Q1_test.parquet

oulad_dashboard/data/ml_Q2_train.parquet
oulad_dashboard/data/ml_Q2_test.parquet

oulad_dashboard/data/ml_Q3_train.parquet
oulad_dashboard/data/ml_Q3_test.parquet

oulad_dashboard/data/ml_Q4_train.parquet
oulad_dashboard/data/ml_Q4_test.parquet
```

together with compact dashboard context datasets such as:

```text
dashboard_registration_context.parquet
dashboard_student_context.parquet
dashboard_weekly_vle.parquet
dashboard_student_assessment.parquet
dashboard_assessments.parquet
dashboard_courses.parquet
```

## Recommendation Evaluation

The notebook evaluates the recommendation behaviour across quarters and checks:

- recommendation coverage;
- number of recommendations per learner;
- recommendation severity;
- behavioural-gap distributions;
- recommendations for at-risk versus successful students;
- prediction/recommendation alignment;
- cluster-specific behavioural differences;
- recommendation safeguards.

The evaluation is retrospective: academic outcome can be used to assess whether the recommendations appropriately concentrate on learners who subsequently experience negative outcomes, but it does not determine the recommendation itself.

The notebook also verifies that:

```text
changing the student's final target does not alter recommendations;
prediction output does not alter behavioural recommendation generation;
undefined AP/spacing indicators do not create recommendations;
Student recommendations are capped and diversified;
prediction coverage is correctly integrated.
```

---

# 7. Relationship Between the Two Pipelines

The execution flow is:

```text
Raw OULAD data
       │
       ▼
final_pipeline_dashboard_deployment.ipynb
       │
       ├── Behavioural features
       ├── Behavioural clusters
       ├── Baseline models
       ├── Cluster-aware models
       ├── LSTM / BiLSTM models
       ├── Model evaluation
       └── Student risk predictions
                    │
                    ▼
       dashboard_student_predictions.csv
                    │
                    ▼
recommendation-pipeline.ipynb
       │
       ├── Successful-peer benchmarks
       ├── Behavioural-gap analysis
       ├── Recommendation prioritisation
       ├── Intervention recommendations
       ├── Recommendation validation
       └── Dashboard-ready exports
                    │
                    ▼
             TrackWise Dashboard
```

Therefore, the notebooks should **not be run in the reverse order**.

---

# 8. Launch the TrackWise Dashboard

After both notebooks have completed successfully, close Jupyter if desired and return to the repository root:

```bash
cd ..
```

From:

```text
oulad-clustered-student-engagement/
```

run:

```bash
python -m streamlit run oulad_dashboard/app.py
```

Alternatively:

```bash
streamlit run oulad_dashboard/app.py
```

The application should open automatically in the browser.

If it does not, open:

```text
http://localhost:8501
```

---

# 9. Dashboard Views

TrackWise provides three role-based interfaces.

### Student

Provides an individual learner with:

- current behavioural profile;
- risk context;
- behavioural strengths;
- behavioural improvement opportunities;
- anonymous successful-peer benchmarks;
- personalised support recommendations.

### Instructor

Provides instructors with:

- cohort-level student monitoring;
- learners requiring attention;
- behavioural risk indicators;
- individual student drill-down;
- recommended support actions;
- behavioural cluster information.

### Administrator

Provides:

- institution/programme-level analytics;
- module and presentation comparisons;
- intervention workload information;
- aggregate risk patterns;
- withdrawal/registration context;
- recommendation and support summaries.

---

# Quick Execution Summary

After cloning the repository and placing the supplied OULAD files in `data/raw/`:

```bash
cd oulad-clustered-student-engagement

python -m pip install -r oulad_dashboard/requirements.txt
python -m pip install jupyter

cd notebooks
jupyter notebook
```

Run, in order:

```text
1. final_pipeline_dashboard_deployment.ipynb
2. recommendation-pipeline.ipynb
```

After both notebooks finish:

```bash
cd ..

python -m streamlit run oulad_dashboard/app.py
```

Then open:

```text
http://localhost:8501
```

## Important

The raw OULAD files must be placed at:

```text
data/raw/
```

before either notebook is executed.

The `final_pipeline_dashboard_deployment.ipynb` notebook must complete before `recommendation-pipeline.ipynb`, because the recommendation pipeline loads the prediction output generated by the modelling pipeline.