# oulad-clustered-student-engagement
OULAD-based project that clusters students using early engagement behaviour to analyse academic outcomes and explore early intervention strategies in online learning.

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
