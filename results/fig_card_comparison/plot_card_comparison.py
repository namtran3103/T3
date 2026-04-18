"""
Plot the cardinality-comparison figure (3 subplots: p50 / p90 / avg q-error).

Reads act_act.txt, act_est.txt, est_est.txt from the same directory,
parses the summary line written by infer_card_comparison.py, and produces
card_comparison.png in the same directory.
"""

import os
import re
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCENARIOS = [
    ("act_act", "Exact Train, Exact Eval.",       "#4472C4", ""),
    ("act_est", "Exact Train, Estimated Eval.",    "#C0392B", "//"),
    ("est_est", "Estimated Train, Estimated Eval.","#27AE60", "\\\\"),
]

_PATTERN = re.compile(
    r"avg=(?P<avg>[0-9.]+)\s+p50=(?P<p50>[0-9.]+)\s+p90=(?P<p90>[0-9.]+)"
)


def parse_txt(stem: str) -> dict[str, float]:
    path = os.path.join(SCRIPT_DIR, f"{stem}.txt")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _PATTERN.search(line)
            if m:
                return {k: float(v) for k, v in m.groupdict().items()}
    raise ValueError(f"Could not parse metrics from {path}")


def main() -> None:
    data = {}
    for stem, *_ in SCENARIOS:
        data[stem] = parse_txt(stem)

    metrics = [
        ("p50", "p50 Q-Error"),
        ("p90", "p90 Q-Error"),
        ("avg", "Avg Q-Error"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(10, 4.5))

    bar_handles = []

    for col, (metric_key, ylabel) in enumerate(metrics):
        ax = axes[col]
        values = [data[stem][metric_key] for stem, *_ in SCENARIOS]
        x = np.arange(len(SCENARIOS))
        width = 0.55

        bars_this = []
        for i, ((stem, label, color, hatch), val) in enumerate(
            zip(SCENARIOS, values)
        ):
            bar = ax.bar(
                x[i], val, width,
                color=color, hatch=hatch,
                edgecolor="black", linewidth=0.6, zorder=3,
            )
            bars_this.append(bar)
            ax.annotate(
                f"{val:.2f}",
                xy=(x[i], val),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=9,
            )

        if col == 0:
            bar_handles = bars_this

        ax.set_ylim(1.0, max(values) * 1.18)
        ax.set_xticks(x)
        ax.set_xticklabels([""] * len(SCENARIOS))
        ax.set_ylabel(ylabel, fontsize=11)
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax.set_axisbelow(True)

    axes[1].set_xlabel("Cardinalities for Model Training and Evaluation", fontsize=11)

    fig.legend(
        handles=bar_handles,
        labels=[label for _, label, *_ in SCENARIOS],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=True,
        fontsize=10,
    )

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)

    out_path = os.path.join(SCRIPT_DIR, "card_comparison.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
