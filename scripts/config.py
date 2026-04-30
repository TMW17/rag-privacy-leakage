"""
config.py
=========
Centralized Path Configuration

Every script in this project imports its file paths from this module.
This ensures that:
  1. All scripts agree on where data lives (no hardcoded paths)
  2. Moving the project to a different machine requires changing
     only this one file
  3. Directory creation is handled automatically at import time

DIRECTORY LAYOUT
----------------
All paths are relative to PROJECT_ROOT, which is the 'code/' directory
(one level above 'scripts/'). Every script must be run from the
'code/' directory, or the paths will not resolve correctly.

    PFE/code/                          ← PROJECT_ROOT (run scripts from here)
    ├── data/
    │   ├── ground_truth/              ← Generated ground truth corpus
    │   │   ├── ground_truth.json          Full corpus (4 document classes)
    │   │   ├── ground_truth_index.json    Flat lookup by document_id
    │   │   └── ground_truth_annotations.json  Entity-level PII annotations
    │   └── synthetic/                 ← Reserved for future datasets
    ├── experiment_logs/               ← Phase 2-4 experiment run logs
    ├── experiments/                   ← Attack scripts and configs
    ├── results/
    │   ├── reidentification_risk.json     k-anonymity / l-diversity analysis
    │   └── kappa_results.json             Inter-annotator agreement scores
    └── scripts/
        ├── config.py                  ← THIS FILE
        ├── generate_dataset.py        ← Step 1: corpus generation (run directly)
        ├── annotate_dataset.py        ← Step 2: PII annotation (run directly)
        ├── evaluation_engine.py       ← Step 3: L and S detection (imported, not run directly)
        ├── reidentification_risk.py   ← Step 4: k-anonymity / l-diversity (run directly)
        ├── kappa_validation.py        ← Step 5: inter-annotator agreement (run directly)
        └── validate_ground_truth.py   ← Step 6: pre-flight consistency gate (run directly)


"""

import os

# =================================================================
#  PROJECT ROOT
#
#  Computed dynamically: this file lives in code/scripts/,
#  so the project root (code/) is one directory above.
#  This works regardless of where Python is invoked from,
#  as long as the file structure is intact.
# =================================================================

# Step 1: os.path.abspath(__file__)
#         Converts the path of THIS file to an absolute path, resolving any
#         symlinks or relative references. This makes the path portable — it
#         works whether the script is run directly, via -m, or from a symlink.
# Step 2: os.path.dirname(...)
#         Strips the filename to get the directory that contains this file.
#         Result: /path/to/PFE/code/scripts/
# Step 3: os.path.dirname(_THIS_DIR)
#         Goes one level up from scripts/ to reach the project root code/.
#         Result: /path/to/PFE/code/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_THIS_DIR)


# =================================================================
#  DIRECTORY PATHS
# =================================================================

# ── Data directories ──
DATA_DIR          = os.path.join(PROJECT_ROOT, "data")
GROUND_TRUTH_DIR  = os.path.join(DATA_DIR, "ground_truth")
SYNTHETIC_DIR     = os.path.join(DATA_DIR, "synthetic")

# ── Output directories ──
RESULTS_DIR       = os.path.join(PROJECT_ROOT, "results")
EXPERIMENT_LOGS_DIR = os.path.join(PROJECT_ROOT, "experiment_logs")
EXPERIMENTS_DIR   = os.path.join(PROJECT_ROOT, "experiments")

# ── Scripts directory (where this file lives) ──
SCRIPTS_DIR       = os.path.join(PROJECT_ROOT, "scripts")


# =================================================================
#  FILE PATHS — Ground Truth Corpus
#
#  These are the three core files produced by generate_dataset.py
#  and annotate_dataset.py. Every experiment in Phases 2-4 reads
#  from these files.
# =================================================================

# Full corpus with metadata header (4 document classes)
GROUND_TRUTH_FILE = os.path.join(GROUND_TRUTH_DIR, "ground_truth.json")

# Flat dictionary keyed by document_id for O(1) lookup
GROUND_TRUTH_INDEX_FILE = os.path.join(GROUND_TRUTH_DIR, "ground_truth_index.json")

# Entity-level PII annotations (the answer key for evaluation)
ANNOTATIONS_FILE = os.path.join(GROUND_TRUTH_DIR, "ground_truth_annotations.json")


# =================================================================
#  FILE PATHS — Analysis Results
#
#  These are produced by the analysis scripts and stored in
#  the results/ directory.
# =================================================================

# k-anonymity and l-diversity analysis
REIDENTIFICATION_RISK_FILE = os.path.join(RESULTS_DIR, "reidentification_risk.json")

# Inter-annotator agreement scores
KAPPA_RESULTS_FILE = os.path.join(RESULTS_DIR, "kappa_results.json")


# =================================================================
#  AUTOMATIC DIRECTORY CREATION
#
#  When this module is imported, all required directories are
#  created if they do not already exist. This prevents FileNotFoundError
#  when scripts try to write output files.
# =================================================================

_REQUIRED_DIRS = [
    GROUND_TRUTH_DIR,
    SYNTHETIC_DIR,
    RESULTS_DIR,
    EXPERIMENT_LOGS_DIR,
    EXPERIMENTS_DIR,
]

for directory in _REQUIRED_DIRS:
    # exist_ok=True means: do nothing if the directory already exists.
    # Without this flag, Python would raise FileExistsError on the second run.
    os.makedirs(directory, exist_ok=True)


# =================================================================
#  PROJECT-WIDE CONSTANTS
#
#  These are the single source of truth for values that appear in
#  both code and the LaTeX thesis. If a value changes here it must
#  also change in the thesis (and vice versa). See §9, invariant 1.
# =================================================================

# Authorization thresholds for Definition 1 (L).
# Keys are string names matching AttackerProfile.value in evaluation_engine.py.
# Thesis §4, Table: "Authorization thresholds — single source of truth".
#   Internal (2): may see severity-2 behavioral data legitimately
#   External (0): no corpus access at all
#   Admin    (3): already sees 2/3 via admin tools; chat leaking 4/5 is the threat
AUTHORIZATION_LEVELS = {
    "Internal": 2,
    "External": 0,
    "Admin":    3,
}

# Corpus seed — both random.seed and Faker.seed are set to this value
# in generate_dataset.py to guarantee the same 155 documents on every run.
CORPUS_SEED = 42
