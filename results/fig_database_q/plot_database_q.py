"""
Per-database q-error bar chart (p50 / p90 / avg) for query-level act models.

Reads results/models/query-level/act/0_results.txt, which contains one summary
line per holdout database in the format written by inference_zeroshot_holdout.py:
  Test set (db, N queries): q-error avg=X p50=Y p90=Z model=...

Produces database_q.png in the same directory as this script.
"""

import re
import os
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.normpath(os.path.join(
    SCRIPT_DIR, '..', 'models', 'query-level', 'act', '0_results.txt'
))

LINE_RE = re.compile(
    r'Test set \((\w+),.*?q-error avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)'
)

DB_LABELS = {
    'tpc_h':          'TPC-H',
    'tpc_ds':         'TPC-DS',
    'accidents':      'Accident',
    'airline':        'Airline',
    'baseball':       'Baseball',
    'basketball':     'Basketball',
    'carcinogenesis': 'Carcinogenesis',
    'consumer':       'Consumer',
    'credit':         'Credit',
    'employee':       'Employee',
    'fhnk':           'Fhnk',
    'financial':      'Financial',
    'geneea':         'Geneea',
    'genome':         'Genome',
    'hepatitis':      'Hepatitis',
    'imdb_full':      'Imdb_full',
    'movielens':      'Movielens',
    'seznam':         'Seznam',
    'ssb':            'Ssb',
    'tournament':     'Tournament',
    'walmart':        'Walmart',
}


def parse_file(path: str):
    dbs, avgs, p50s, p90s = [], [], [], []
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                db = m.group(1)
                dbs.append(DB_LABELS.get(db, db.capitalize()))
                avgs.append(float(m.group(2)))
                p50s.append(float(m.group(3)))
                p90s.append(float(m.group(4)))
    return dbs, avgs, p50s, p90s


if __name__ == '__main__':
    dbs, avgs, p50s, p90s = parse_file(INPUT)
    if not dbs:
        print(f"No data found in {INPUT}")
        raise SystemExit(1)

    n = len(dbs)
    x = np.arange(n)
    width = 0.22

    # A4 text width ≈ 6.3 in; use 6.5 × 3.2 so the figure fills \textwidth
    fig, ax = plt.subplots(figsize=(6.5, 3.2))

    bar50 = ax.bar(x - width, p50s, width, color='#4472C4',
                   edgecolor='black', linewidth=0.5, label='p50', zorder=3)
    bar90 = ax.bar(x,         p90s, width, color='#C0392B', hatch='//',
                   edgecolor='black', linewidth=0.5, label='p90', zorder=3)
    barav = ax.bar(x + width, avgs, width, color='#27AE60', hatch='\\\\',
                   edgecolor='black', linewidth=0.5, label='avg', zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(dbs, rotation=55, ha='right', fontsize=7)
    ax.set_ylabel('Q-Error', fontsize=9)
    ax.set_xlabel('Database Instance', fontsize=9)
    ax.tick_params(axis='y', labelsize=8)
    ax.set_ylim(bottom=1)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    ax.legend(
        handles=[bar50, bar90, barav],
        labels=['p50', 'p90', 'avg'],
        loc='upper center',
        bbox_to_anchor=(0.5, -0.52),
        ncol=3,
        frameon=True,
        fontsize=9,
    )

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.38)
    out_path = os.path.join(SCRIPT_DIR, 'database_q.png')
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
