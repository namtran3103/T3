import re
import os
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

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


def parse_p50(path):
    result = {}
    with open(path) as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                db = m.group(1)
                label = DB_LABELS.get(db, db.capitalize())
                result[label] = float(m.group(2))
    return result


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)

    query    = parse_p50(os.path.join(data_dir, 'holdout_query_est.txt'))
    pipeline = parse_p50(os.path.join(data_dir, 'holdout_pipeline_est.txt'))
    tuple_   = parse_p50(os.path.join(data_dir, 'holdout_tuple_est.txt'))

    dbs = list(query.keys())

    query_vals    = [query.get(db, float('nan'))    for db in dbs]
    pipeline_vals = [pipeline.get(db, float('nan')) for db in dbs]
    tuple_vals    = [tuple_.get(db, float('nan'))   for db in dbs]

    n = len(dbs)
    x = np.arange(n)
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(10, n * 0.6), 5))

    bar_q = ax.bar(x - width, query_vals,    width, color='#4472C4',
                   edgecolor='black', linewidth=0.6, label='Query-level', zorder=3)
    bar_p = ax.bar(x,         pipeline_vals, width, color='#C0392B', hatch='//',
                   edgecolor='black', linewidth=0.6, label='Pipeline-level', zorder=3)
    bar_t = ax.bar(x + width, tuple_vals,    width, color='#27AE60', hatch='\\\\',
                   edgecolor='black', linewidth=0.6, label='Tuple-level', zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(dbs, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Q-Error (p50)', fontsize=11)
    ax.set_xlabel('Database Instance', fontsize=11)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=1)

    ax.legend(
        handles=[bar_q, bar_p, bar_t],
        labels=['Query-level', 'Pipeline-level', 'Tuple-level'],
        loc='upper center',
        bbox_to_anchor=(0.5, -0.38),
        ncol=3,
        frameon=True,
        fontsize=10,
    )

    fig.tight_layout()
    out_path = os.path.join(data_dir, 'levels_est.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
