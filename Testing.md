# Testing

## Umbra query prediction and feature vectors

Script: `testing/run_umbra_prediction.py` — runs Umbra query prediction and prints the **feature vector for each pipeline**.

**Requirements:** `pip install -r requirements.txt`

### Usage

**From SQL file** (requires Umbra server running):

```bash
python -m testing.run_umbra_prediction queries/tpch/5.sql --server http://localhost:8080 --db tpchSf1
```

**From existing Umbra plan JSON** (no server needed):

```bash
python -m testing.run_umbra_prediction --plan-json data/tpchSf1/fixed/tpchSf1_q5.json --db tpchSf1
```

**With model predictions** (per-pipeline and total runtime):

```bash
python -m testing.run_umbra_prediction --plan-json data/tpchSf1/fixed/tpchSf1_q5.json --db tpchSf1 --model model.txt
```

**Print all feature dimensions** (including zeros):

```bash
python -m testing.run_umbra_prediction --plan-json data/tpchSf1/fixed/tpchSf1_q5.json --db tpchSf1 -v
```

### Options

| Option | Description |
|--------|-------------|
| `sql_file` | Path to SQL file (e.g. `queries/tpch/5.sql`). Use with `--server`. |
| `--plan-json PATH` | Path to existing Umbra plan JSON (e.g. `data/tpchSf1/fixed/tpchSf1_q5.json`). |
| `--server URL` | Umbra server URL (default: `http://localhost:8080`). |
| `--db NAME` | Database name (default: `tpchSf1`). Must match schema (e.g. tpch → tpchSf1). |
| `--model PATH` | Optional path to model file (e.g. `model.txt`) for pipeline runtime prediction. |
| `-v`, `--verbose` | Print all feature dimensions; otherwise only non-zero. |

### Output

For each pipeline: index, scan cardinality, and feature vector (name → value). With `--model`: predicted runtime per pipeline and total (seconds).
