import os
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'

MODELS  = ['T3 (Rieger, Neumann)', 'ZeroShot', 'Ours']
VALUES  = [1.23, 1.5979, 1.8920]
LABELS  = ['1.23', '1.60', '1.89']
COLORS  = ['#4472C4', '#C0392B', '#27AE60']
HATCHES = ['',        '//',       '\\\\']

if __name__ == '__main__':
    x = np.arange(len(MODELS))
    width = 0.5

    fig, ax = plt.subplots(figsize=(4, 3))

    bars = []
    for i, (model, val, label, color, hatch) in enumerate(
            zip(MODELS, VALUES, LABELS, COLORS, HATCHES)):
        bar = ax.bar(x[i], val, width, color=color, hatch=hatch,
                     edgecolor='black', linewidth=0.6, zorder=3)
        bars.append(bar)
        ax.annotate(label,
                    xy=(x[i], val),
                    xytext=(0, 4),
                    textcoords='offset points',
                    ha='center', va='bottom',
                    fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(['']*len(MODELS))
    ax.set_xlabel('Model', fontsize=11)
    ax.set_ylabel('JOB Q-Error (avg)', fontsize=11)
    ax.set_ylim(1, max(VALUES) * 1.12)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    ax.legend(
        handles=bars,
        labels=MODELS,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.15),
        ncol=3,
        frameon=True,
        fontsize=10,
    )

    fig.tight_layout()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, 'avg_comparison.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
