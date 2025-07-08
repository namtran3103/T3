from matplotlib import pyplot as plt
from matplotlib.colors import to_rgba

from src.evaluation import QueryEstimationCache
from src.figures.acc_comparison import get_competitor_numbers, get_test_numbers
from src.figures.infra import setup_matplotlib_latex_font, get_hex_colors, get_figure_path, get_figure_format
from src.train import optimize_all


def get_latencies() -> dict:
    """
    unit is ms
    """
    return {
        "hilprecht": {"nn": 50, "avg": 50},
        "stage": {"cache": 0.002, "dt": 1, "nn": 30, "avg": 0.3},
        "t3": {"dt": 0.004, "avg": 0.004},
        "autowlm": {"dt": 0.1, "avg": 0.1},
    }


def get_latency_table() -> str:
    latencies = get_latencies()
    return f"""  \\begin{{tabular}}{{r|r r r r}}
     & Cache & DT & NN & Avg \\
    \\hline
    Zero Shot \\cite{{hilprecht2022vldb}} & - & - & {latencies["hilprecht"]["nn"]}ms & {latencies["hilprecht"]["avg"]}ms\\\\
    Stage \\cite{{stage}} & $\\sim${latencies["stage"]["cache"] * 1000:.0f}us & $\\sim${latencies["stage"]["dt"]}ms & $\\sim${latencies["stage"]["nn"]}ms & $\\sim${latencies["stage"]["avg"] * 1000:.0f}us\\\\
    T3 (ours) & - & {latencies["t3"]["dt"] * 1000:.0f}us & - & \\textbf{{{latencies["t3"]["avg"] * 1000:.0f}us}}\\
  \\end{{tabular}}"""


def latency_acc_figure(estimation_cache: QueryEstimationCache):
    setup_matplotlib_latex_font()
    auto_wlm, stage, zero_shot = get_competitor_numbers()
    t3 = get_test_numbers(estimation_cache)
    latencies = get_latencies()
    names = ["T3 (ours)", "Zero Shot", "Stage*", "AutoWLM*"]
    latencies = [
        latencies["t3"]["avg"],
        latencies["hilprecht"]["avg"],
        latencies["stage"]["avg"],
        latencies["autowlm"]["avg"],
    ]
    accuracies = [t3["p50"], zero_shot["p50"], stage["p50"], auto_wlm["p50"]]
    colors = get_hex_colors(["my_blue", "my_red", "my_green", "my_yellow"])
    markers = ["o", "s", "^", "D"]
    plt.figure(figsize=(4, 3))
    for x, y, name, color, marker in zip(latencies, accuracies, names, colors, markers):
        plt.scatter(x, y, color=color, marker=marker, label=name, s=100)
        plt.annotate(
            name,
            (x, y),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=14,
        )

    # "better" arrow in bottom left corner
    bbox_props = dict(boxstyle="larrow", fc=to_rgba("grey", 0.30), ec="b", lw=0)
    t = plt.text(
        1e-1, 2.45, "better", ha="left", va="bottom", rotation=45, size=15, bbox=bbox_props, color="white", alpha=0.8
    )
    bb = t.get_bbox_patch()
    bb.set_boxstyle("larrow", pad=0.5)

    # precise limits for the arrow and labels
    plt.ylim(0.90, 4.75)
    plt.xlim(0.0007, 90)
    plt.xscale("log")
    plt.xticks([1e-3, 1e-2, 1e-1, 1e0, 1e1])
    plt.xlabel("Avg. Latency in ms (log)")
    plt.ylabel("Prediction Error\np50 Q-Error")
    plt.savefig(f"{get_figure_path()}/latency_acc.{get_figure_format()}", bbox_inches="tight")


def main():
    print(get_latency_table())
    model = optimize_all(True)
    estimation_cache = QueryEstimationCache(model, True)
    latency_acc_figure(estimation_cache)


if __name__ == "__main__":
    main()
