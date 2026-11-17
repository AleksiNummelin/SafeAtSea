#!/usr/bin/env bash
# Submit the Safe@Sea point extraction job to CSC Roihu's 'small' queue.
#
# Usage:
#   chmod +x submit_safeatsea_point_extraction_small.sh
#   ./submit_safeatsea_point_extraction_small.sh
#
# Edit the CSC project account before running. The default value is a placeholder.

set -euo pipefail

CSC_ACCOUNT="${CSC_ACCOUNT:-project_2010671}"
OUTPUT_DIR="${OUTPUT_DIR:-$PWD}"
START_DATE="${START_DATE:-2026-01-01}"
END_DATE="${END_DATE:-2026-10-31}"
SCRIPT_PATH="${SCRIPT_PATH:-$PWD/safeatsea_point_extraction.py}"
LOG_DIR="${LOG_DIR:-$PWD/logs}"
mkdir -p "$LOG_DIR"

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Python script not found: $SCRIPT_PATH"
  exit 1
fi

if [[ "$CSC_ACCOUNT" == "<your-csc-project-account>" ]]; then
  echo "Set CSC_ACCOUNT to your CSC project account before submitting, e.g.:"
  echo "  export CSC_ACCOUNT=project_2001234"
  echo "or edit this script and replace the placeholder."
  exit 1
fi

SBATCH_SCRIPT=$(mktemp)
cat > "$SBATCH_SCRIPT" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=safeatsea-point-extraction
#SBATCH --account=${CSC_ACCOUNT}
#SBATCH --partition=small
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=${LOG_DIR}/safeatsea-point-%j.out
#SBATCH --error=${LOG_DIR}/safeatsea-point-%j.err

set -euo pipefail

module purge || true
module load python-geo || true

python3 "$SCRIPT_PATH" \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --output-dir "$OUTPUT_DIR"
EOF

chmod +x "$SBATCH_SCRIPT"

sbatch "$SBATCH_SCRIPT"
rm -f "$SBATCH_SCRIPT"
