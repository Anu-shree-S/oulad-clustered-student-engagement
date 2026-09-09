# TrackWise dashboard redesign

The dashboard is now a role-based support product rather than an EDA interface.

## Navigation
- No sidebar navigation.
- Course/module/stage filters appear in a top control ribbon.
- Role pages are organised with horizontal tabs.

## Student
- Private assigned learner only; pseudonymous ID.
- Supportive language, strengths first, no raw risk probability.
- Compact progress trend, pedagogical learning-habit cards, max three personalised recommendations.
- Learning pattern is descriptive, not an identity label.
- Support plan and privacy explanations included.

## Instructor
- Action-first overview and priority queue.
- Behavioural explanation separated from prediction signal.
- Learner profile, recommendation actions and illustrative intervention tracking.
- Cohort-level common issues identify teaching opportunities.

## Administrator
- Aggregate-only operational analytics.
- Module support concentration and intervention workload.
- Aggregate fairness/support-exposure review.
- Governance and human oversight.
- Historical outcomes moved to a separate Research tab.

## Data inputs
Place raw OULAD CSV files in `data/` or `data/raw/`.

Place recommendation outputs in `data/recommendations/`:
- `recommendation_summary_Q1.parquet` ... `Q4`
- `recommendation_details_Q1.parquet` ... `Q4`
- `cluster_profiles_Q1.json` ... `Q4`
- `recommendation_quarter_comparison.csv`

Place behavioural tables in `data/`:
- `ml_Q1_test.parquet` ... `ml_Q4_test.parquet`
- train tables are optional for the dashboard itself.

Optional prediction output can be added under `data/predictions/` using one of:
- `student_predictions.parquet/csv`
- `dashboard_predictions.parquet/csv`

Expected prediction columns are `id_student`, `code_module`, `code_presentation`, `quarter`, and a probability column such as `risk_probability`. Optional: `model_name`, `threshold`, `predicted_class`.
