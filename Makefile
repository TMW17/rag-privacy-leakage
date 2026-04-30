.PHONY: all clean validate

# =================================================================
#  One-command full Phase 1 pipeline rebuild.
#  Targets are the output files; make skips steps whose outputs
#  are already newer than their inputs.
# =================================================================

all: data/ground_truth/ground_truth.json \
     data/ground_truth/ground_truth_annotations.json \
     results/reidentification_risk.json \
     results/kappa_results.json

# Step 1 — generate the 155-document synthetic corpus
data/ground_truth/ground_truth.json:
	python scripts/generate_dataset.py

# Step 2 — annotate with 2,315 entity-level PII labels
data/ground_truth/ground_truth_annotations.json: data/ground_truth/ground_truth.json
	python scripts/annotate_dataset.py

# Step 4 — k-anonymity / l-diversity re-identification analysis
results/reidentification_risk.json: data/ground_truth/ground_truth.json
	python scripts/reidentification_risk.py

# Step 5 — inter-annotator agreement (Cohen's kappa)
results/kappa_results.json:
	python scripts/kappa_validation.py

# Run the pre-flight consistency gate (must exit 0 before Phase 2)
validate: data/ground_truth/ground_truth_annotations.json
	python scripts/validate_ground_truth.py

# Remove all generated artefacts so `make all` runs from scratch
clean:
	rm -f data/ground_truth/ground_truth.json \
	      data/ground_truth/ground_truth_index.json \
	      data/ground_truth/ground_truth_annotations.json \
	      results/reidentification_risk.json \
	      results/kappa_results.json
