import re
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['font.family'] = 'serif'

LINE_RE = re.compile(
    r'Test set \((\w+),.*?q-error avg=[\d.]+ p50=([\d.]+) p90=[\d.]+'
)

DB_LABELS = {
    'tpc_h': 'TPC-H',
    'tpc_ds': 'TPC-DS',
    'accidents': 'Accident',
    'airline': 'Airline',
    'baseball': 'Baseball',
    'basketball': 'Basketball',
    'carcinogenesis': 'Carcinogenesis',
    'consumer': 'Consumer',
    'credit': 'Credit',
    'employee': 'Employee',
    'fhnk': 'Fhnk',
    'financial': 'Financial',
    'geneea': 'Geneea',
    'genome': 'Genome',
    'hepatitis': 'Hepatitis',
    'imdb': 'Imdb',
    'imdb_full': 'Imdb_full',
    'job': 'Job',
    'movielens': 'Movielens',
    'seznam': 'Seznam',
    'ssb': 'Ssb',
    'tournament': 'Tournament',
    'walmart': 'Walmart',
}

PANELS = [
    ('holdout_query_act.txt',    'Exact Train, Exact Eval.',       '#4472C4', '',     ),
    ('exact_train_est_eval.txt', 'Exact Train, Estimated Eval.',   '#C0392B', '//',   ),
    ('holdout_query_est.txt',    'Estimated Train, Estimated Eval.','#27AE60', '\\\\',),
]


def parse_p50(path):
    result = {}
    with open(path) as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                label = DB_LABELS.get(m.group(1), m.group(1).capitalize())
                result[label] = float(m.group(2))
    return result


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir   = os.path.dirname(script_dir)

    datasets = [(label, color, hatch, parse_p50(os.path.join(data_dir, fname)))
                for fname, label, color, hatch in PANELS]

    dbs = list(datasets[0][3].keys())
    n = len(dbs)
    x = np.arange(n)
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(12, n * 0.7), 6.5))

    bars = []
    for i, (label, color, hatch, data) in enumerate(datasets):
        vals = [data.get(db, float('nan')) for db in dbs]
        bar = ax.bar(x + (i - 1) * width, vals, width,
                     color=color, hatch=hatch,
                     edgecolor='black', linewidth=0.6,
                     label=label, zorder=3)
        bars.append(bar)

    ax.set_xticks(x)
    ax.set_xticklabels(dbs, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Q-Error (p50)', fontsize=11)
    ax.set_xlabel('Database Instance', fontsize=11)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=1)

    leg = ax.legend(
        handles=bars,
        labels=[label for label, *_ in datasets],
        title='Cardinalities for Model Training and Evaluation',
        loc='upper center',
        bbox_to_anchor=(0.5, -0.48),
        ncol=1,
        frameon=True,
        fontsize=9,
    )
    leg.get_title().set_fontsize(9)
    leg.get_title().set_fontweight('bold')

    fig.tight_layout()
    out_path = os.path.join(data_dir, 'holdout_query_triple.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
