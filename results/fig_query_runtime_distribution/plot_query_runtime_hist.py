import json
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'

_REPO = Path(__file__).resolve().parents[2]
PARSED_PLANS_DIR = _REPO / "zero-shot-data" / "runs" / "parsed_plans"

if __name__ == '__main__':
    runtimes_sec = []
    for db_path in sorted(PARSED_PLANS_DIR.iterdir()):
        if not db_path.is_dir():
            continue
        for json_file in sorted(db_path.glob("*.json")):
            with open(json_file) as f:
                data = json.load(f)
            for plan in data['parsed_plans']:
                runtimes_sec.append(plan['plan_runtime'] / 1000.0)

    runtimes_sec = np.array(runtimes_sec)

    log_min = np.floor(np.log10(runtimes_sec.min()))
    log_max = np.ceil(np.log10(runtimes_sec.max()))
    bins = np.logspace(log_min, log_max, num=30)

    fig, ax = plt.subplots(figsize=(7, 4))

    ax.hist(runtimes_sec, bins=bins, color='#4472C4', edgecolor='black', linewidth=0.6, zorder=3)

    ax.set_xscale('log')
    ax.set_xlabel('Running Time of Query in Seconds', fontsize=11)
    ax.set_ylabel('Frequency', fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, 'query_runtime_hist.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
