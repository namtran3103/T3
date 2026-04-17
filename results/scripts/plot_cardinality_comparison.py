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

    exact_exact   = parse_p50s(os.path.join(data_dir, 'holdout_query_act.txt'))
    exact_est     = parse_p50s(os.path.join(data_dir, 'exact_train_est_eval.txt'))
    est_est       = parse_p50s(os.path.join(data_dir, 'holdout_query_est.txt'))

    stats = {
        'Median':  [np.median(exact_exact), np.median(exact_est), np.median(est_est)],
        'Average': [np.mean(exact_exact),   np.mean(exact_est),   np.mean(est_est)],
    }

    groups = list(stats.keys())
    n_groups = len(groups)
    width = 0.22
    gap = 0.9
    group_centers = np.arange(n_groups) * gap
    offsets = np.array([-1, 0, 1]) * width

    LABELS  = ['Exact Train, Exact Eval.', 'Exact Train, Estimated Eval.', 'Estimated Train, Estimated Eval.']
    COLORS  = ['#4472C4', '#C0392B', '#27AE60']
    HATCHES = ['', '//', '\\\\']

    fig, ax = plt.subplots(figsize=(6, 5))

    bar_ee = bar_eE = bar_EE = None
    for g_idx, group in enumerate(groups):
        vals = stats[group]
        cx = group_centers[g_idx]

        bar_ee = ax.bar(cx + offsets[0], vals[0], width, color=COLORS[0],
                        hatch=HATCHES[0], edgecolor='black', linewidth=0.6,
                        label=LABELS[0] if g_idx == 0 else '_', zorder=3)
        bar_eE = ax.bar(cx + offsets[1], vals[1], width, color=COLORS[1],
                        hatch=HATCHES[1], edgecolor='black', linewidth=0.6,
                        label=LABELS[1] if g_idx == 0 else '_', zorder=3)
        bar_EE = ax.bar(cx + offsets[2], vals[2], width, color=COLORS[2],
                        hatch=HATCHES[2], edgecolor='black', linewidth=0.6,
                        label=LABELS[2] if g_idx == 0 else '_', zorder=3)

    ax.set_xticks(group_centers)
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylabel('Q-Error (p50)', fontsize=11)
    ax.set_xlabel('Median and Average over all per-Database p50 Q-Errors', fontsize=11)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=1)

    leg = ax.legend(
        handles=[bar_ee, bar_eE, bar_EE],
        labels=LABELS,
        title='Cardinalities for Model Training and Evaluation',
        loc='upper center',
        bbox_to_anchor=(0.5, -0.20),
        ncol=1,
        frameon=True,
        fontsize=9,
    )
    leg.get_title().set_fontsize(9)
    leg.get_title().set_fontweight('bold')

    fig.tight_layout()
    out_path = os.path.join(data_dir, 'cardinality_comparison.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
