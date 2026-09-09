# oulad-clustered-student-engagement
OULAD-based project that clusters students using early engagement behaviour to analyse academic outcomes and explore early intervention strategies in online learning.

## TrackWise conference application

**Behavioural Learning Analytics for Early Student Support**

From the repository root, using Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

If the `streamlit` command is not on PATH, use `python -m streamlit run app.py`.
On the current Windows workstation, the WindowsApps `python` alias is unavailable;
the existing interpreter at `C:\Users\Anushree\AppData\Local\Programs\Python\Python310\python.exe`
was used for validation. In PowerShell:

```powershell
& 'C:\Users\Anushree\AppData\Local\Programs\Python\Python310\python.exe' -m streamlit run app.py
```

The landing page offers Student, Instructor and Administrator demo personas without
passwords. Identity and permissions are stored in the Streamlit session. To change
role, use **Sign out** and choose another persona at login.

- Students see their assigned enrolment and anonymous class benchmarks.
- Instructors see assigned module/presentation pairs and learners in those cohorts.
- Administrators see institutional/group analytics and aggregate CSV reports.

The original `Trackwise Dashboard/Trackwise.py` and `Trackwise Dashboard/pages/Student.py`,
`Instructor.py`, and `Admin.py` remain compatibility launchers for the same login.
The analytics have one source of truth under `pages/`.

### Data and persona configuration

The application reads the original `studentInfo.csv`, `studentVle.csv`,
`studentAssessment.csv`, and `assessments.csv` from `data/` or `data/raw/`.
An optional `TRACKWISE_DATA_DIR` environment variable can select another directory.
All four files must be in that directory. Missing or malformed data produces an
explanatory message; the app does not generate random substitute data.

Edit [config/demo_users.py](config/demo_users.py) to curate demo personas. By
default the student is chosen deterministically from BBB/2014J if available,
otherwise the first valid enrolment. The instructor gets one existing cohort;
set `modules` to explicit `(module, presentation)` pairs to assign more.
Explicit invalid assignments are rejected. Sign out and back in after changing
persona configuration. Restart the app after replacing the dataset.

Raw OULAD identifiers remain internal join keys. The conference interface uses
`TW-S…` aliases consistently across roles and exports. Aliases remain stable while
the dataset's student IDs stay the same; replacing the dataset can change them.

### Verification and scope

```bash
python -m compileall .
python -m unittest discover -s tests -v
```

The regression tests use small explicitly synthetic CSV fixtures in temporary
directories. They cover login/logout, all role sections, membership checks,
privacy, exports, missing data, invalid assignments, stale navigation and legacy
launchers. They never edit the source dataset.

Priority 1 changes architecture, privacy separation, navigation and demo layout.
`notebooks/final_pipeline.ipynb`, models, feature engineering, recommendation rules
and risk thresholds remain outside this phase. Known inherited limitations and
the browser demo checklist are in [docs/priority-1.md](docs/priority-1.md).

# Dataset

This project uses the Open University Learning Analytics Dataset (OULAD).

Due to GitHub file size limitations, the dataset is not included in this repository. Instead, you can download it directly from the official source:

# 🔗 https://analyse.kmi.open.ac.uk/open-dataset/download

## How to Use the Dataset

Download the dataset from the link above.

Extract the files locally.

Place all CSV files inside the following directory structure:

oulad-clustered-student-engagement/data/raw/<OULAD CSV files>

Ensure the relative path used in the code is preserved:
DATA_RAW = Path("../data/raw")

### Notes

Do not rename the files, as the code expects the original dataset filenames.
Make sure the folder structure matches exactly to avoid file path errors.
The dataset is publicly available for research purposes and provided by the Open University.
