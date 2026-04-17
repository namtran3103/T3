import re
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['font.family'] = 'serif'

LINE_RE = re.compile(
    r'Test set \((\w+),.*?q-error avg=[\d.]+ p50=([\d.]+) p90=[\d.]+'
)


def parse_p50s(path):
    values = []
    with open(path) as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                values.append(float(m.group(2)))
    return values


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)

    q_vals = parse_p50s(os.path.join(data_dir, 'holdout_query_act.txt'))
    p_vals = parse_p50s(os.path.join(data_dir, 'holdout_pipeline_act.txt'))
    t_vals = parse_p50s(os.path.join(data_dir, 'holdout_tuple_act.txt'))

    stats = {
        'Median': [np.median(q_vals), np.median(p_vals), np.median(t_vals)],
        'Average': [np.mean(q_vals),   np.mean(p_vals),   np.mean(t_vals)],
    }

    groups = list(stats.keys())
    n_groups = len(groups)
    width = 0.22
    gap = 0.9
    group_centers = np.arange(n_groups) * gap
    offsets = np.array([-1, 0, 1]) * width

    fig, ax = plt.subplots(figsize=(5, 5))

    bar_q = bar_p = bar_t = None
    for g_idx, group in enumerate(groups):
        vals = stats[group]
        cx = group_centers[g_idx]

        bar_q = ax.bar(cx + offsets[0], vals[0], width, color='#4472C4',
                       edgecolor='black', linewidth=0.6,
                       label='Query-level' if g_idx == 0 else '_', zorder=3)
        bar_p = ax.bar(cx + offsets[1], vals[1], width, color='#C0392B', hatch='//',
                       edgecolor='black', linewidth=0.6,
                       label='Pipeline-level' if g_idx == 0 else '_', zorder=3)
        bar_t = ax.bar(cx + offsets[2], vals[2], width, color='#27AE60', hatch='\\\\',
                       edgecolor='black', linewidth=0.6,
                       label='Tuple-level' if g_idx == 0 else '_', zorder=3)

    ax.set_xticks(group_centers)
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylabel('Q-Error (p50)', fontsize=11)
    ax.set_xlabel('Median and Average over all per-Database p50 Q-Errors', fontsize=11)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=1)

    ax.legend(
        handles=[bar_q, bar_p, bar_t],
        labels=['Query-level', 'Pipeline-level', 'Tuple-level'],
        loc='upper center',
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        frameon=True,
        fontsize=10,
    )

    fig.tight_layout()
    out_path = os.path.join(data_dir, 'summary_act.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
