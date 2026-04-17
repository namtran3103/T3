import re
import os
import math
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['font.family'] = 'serif'

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.dirname(script_dir)

INPUT = os.path.join(data_dir, 'job_zero_t3_results_ql_act_0416.txt')

Q_ERROR_RE = re.compile(r'q_error=([\d.]+)')

if __name__ == '__main__':
    q_errors = []
    with open(INPUT) as f:
        for line in f:
            m = Q_ERROR_RE.search(line)
            if m:
                q_errors.append(float(m.group(1)))

    step = 0.25
    min_val = 1.0
    max_val = max(q_errors)
    n_bins = math.ceil((max_val - min_val) / step)
    edges = [min_val + i * step for i in range(n_bins + 1)]

    counts = [0] * n_bins
    for v in q_errors:
        idx = min(int((v - min_val) / step), n_bins - 1)
        counts[idx] += 1

    centers = [min_val + (i + 0.5) * step for i in range(n_bins)]
    tick_positions = edges
    tick_labels = [str(int(e)) if e == int(e) else '' for e in edges]

    fig, ax = plt.subplots(figsize=(max(8, n_bins * 0.4), 4))

    ax.bar(centers, counts, width=step, color='#4472C4', edgecolor='black', linewidth=0.6, zorder=3)
    ax.set_xlim(min_val, edges[-1])

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=9)
    ax.set_xlabel('Q-Error of Test Queries', fontsize=11)
    ax.set_ylabel('Frequency', fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = os.path.join(data_dir, 'job_zero_t3_results_ql_act_0416_freq.png')
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out}")
