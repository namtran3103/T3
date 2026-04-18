import re
import os
import glob
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'

LINE_RE = re.compile(
    r'Test set \((\w+),.*?q-error avg=([\d.]+) p50=([\d.]+) p90=([\d.]+)'
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


def parse_file(path):
    dbs, p50s, p90s = [], [], []
    with open(path) as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                db = m.group(1)
                label = DB_LABELS.get(db, db.capitalize())
                dbs.append(label)
                p50s.append(float(m.group(3)))
                p90s.append(float(m.group(4)))
    return dbs, p50s, p90s


def plot_file(path):
    dbs, p50s, p90s = parse_file(path)
    if not dbs:
        print(f"No data found in {path}, skipping.")
        return

    n = len(dbs)
    x = np.arange(n)
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, n * 0.7), 5))

    bar50 = ax.bar(x - width / 2, p50s, width, color='#4472C4',
                   edgecolor='black', linewidth=0.6, label='p50', zorder=3)
    bar90 = ax.bar(x + width / 2, p90s, width, color='#C0392B', hatch='//',
                   edgecolor='black', linewidth=0.6, label='p90', zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(dbs, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Q-Error', fontsize=11)
    ax.set_xlabel('Database Instance', fontsize=11)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=1)

    ax.legend(
        handles=[bar50, bar90],
        labels=['p50', 'p90'],
        loc='upper center',
        bbox_to_anchor=(0.5, -0.42),
        ncol=2,
        frameon=True,
        fontsize=10,
    )

    fig.tight_layout()
    out_path = os.path.splitext(path)[0] + '.png'

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    txt_files = glob.glob(os.path.join(data_dir, '*.txt'))
    for f in sorted(txt_files):
        plot_file(f)
