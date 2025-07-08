import json

from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle, ConnectionPatch

from src.figures.infra import setup_matplotlib_latex_font, get_figure_path, get_hex_color, get_figure_format


def latency_scaling_figure():
    setup_matplotlib_latex_font()

    with open("dp/latencyScalingCompiled.json", "r") as file:
        data1 = json.load(file)
    with open("dp/latencyScalingInterpretedST.json", "r") as file:
        data2 = json.load(file)
    with open("dp/latencyScalingInterpretedMT.json", "r") as file:
        data3 = json.load(file)

    x = [float(k) for k in data1.keys()]
    y1 = list(data1.values())
    y2 = list(data2.values())
    y3 = list(data3.values())

    fig, ax = plt.subplots(1, 2, figsize=(6, 2.5))

    # mark avg query size
    avg_query_size = 3
    # print(f"avg query has {avg_query_size} pipelines and {data[str(avg_query_size)]} latency")
    for i in (0, 1):
        ax[i].scatter(avg_query_size, y1[avg_query_size - 1], color=get_hex_color("my_yellow"))

        ax[i].plot(x, y1, color=get_hex_color("my_blue"))
        ax[i].plot(x, y2, color=get_hex_color("my_red"))
        ax[i].plot(x, y3, color=get_hex_color("my_green"))

    focus_x_min, focus_x_max = -0.01, 51
    focus_y_min, focus_y_max = -0.001, 0.1

    ax[0].annotate(
        "Avg Query",
        (avg_query_size, y1[avg_query_size - 1]),
        textcoords="offset points",
        xytext=(3, -5),
        ha="left",
        fontsize=8,
    )
    ax[0].set_xlim(focus_x_min, focus_x_max)
    ax[0].set_ylim(focus_y_min, focus_y_max)
    ax[0].set_xticks([1, 10, 20, 30, 40, 50])

    ax[1].text(1000, y1[-1], "Compiled ST", ha="right", va="bottom", size=11, color="black")
    ax[1].text(240 + 30, y2[240], "Interpreted ST", ha="left", va="bottom", size=11, color="black")
    ax[1].text(500, y3[500] - 0.02, "Interpreted MT", ha="left", va="top", size=11, color="black")

    ax[1].set_ylim(-0.05, 1.05)
    ax[1].set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax[1].set_xticks([1, 250, 500, 750, 1000])

    rect_width = focus_x_max - focus_x_min
    rect_height = focus_y_max - focus_y_min

    rectangle = Rectangle(
        (focus_x_min, focus_y_min),
        rect_width,
        rect_height,
        linewidth=1,
        edgecolor="gray",
        facecolor="none",
        linestyle="-",
    )
    ax[1].add_patch(rectangle)
    con1 = ConnectionPatch(
        xyA=(focus_x_min, focus_y_min),
        xyB=(focus_x_max, focus_y_min),
        coordsA="data",
        coordsB="data",
        linewidth=1,
        axesA=ax[1],
        axesB=ax[0],
        color="gray",
        linestyle=(0, (3, 4)),
    )
    con2 = ConnectionPatch(
        xyA=(focus_x_max, focus_y_max),
        xyB=(focus_x_max, focus_y_max),
        coordsA="data",
        coordsB="data",
        linewidth=1,
        axesA=ax[1],
        axesB=ax[0],
        color="gray",
        linestyle=(0, (3, 4)),
    )
    fig.add_artist(con1)
    fig.add_artist(con2)

    # naming
    ax[0].set_ylabel("Latency in ms")

    fig.savefig(f"{get_figure_path()}/latency_scaling.{get_figure_format()}", bbox_inches="tight")


def main():
    latency_scaling_figure()


if __name__ == "__main__":
    main()
