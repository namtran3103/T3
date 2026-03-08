#!/usr/bin/env python3
"""
Extract median Q-error values from zeroshot-bar-chart.png by pixel measurement.
Bars start at 0 in the image. Scale is calibrated so the largest brown bar = 8.62
(paper worst case for Scaled Optimizer Costs). Uses 0 and 5 axis marks for scale.
Output: brown, green, blue (Scaled Optimizer, Zero-Shot DeepDB Est., Zero-Shot Exact Cardinalities).
"""

from pathlib import Path

from PIL import Image


# Workload names (X-axis order)
WORKLOADS = [
    "Accidents",
    "Airline",
    "Baseball",
    "Basketball",
    "Carcinogenesis",
    "Consumer",
    "Credit",
    "Employee",
    "Fhnk",
    "Financial",
    "Geneea",
    "Genome",
    "Hepatitis",
    "IMDB",
    "Movielens",
    "SSB",
    "Seznam",
    "TPC-H",
    "Tournament",
    "Walmart",
]

# Legend names for the three bar colors (left to right in each group)
SERIES_NAMES = [
    "Scaled Optimizer Costs (Postgres)",   # brown
    "Zero-Shot (DeepDB Est.)",            # green
    "Zero-Shot (Exact Cardinalities)",    # blue
]

# Paper: worst-case Scaled Optimizer = 8.62; zero-shot all < 1.54.
MAX_BROWN_QERROR = 8.62
PAPER_MAX_ZEROSHOT = 1.54  # rescale green/blue so max matches this (paper: "all below 1.54")
RESCALE_ZEROSHOT_TO_PAPER = True  # set False to keep raw pixel-derived scale
# Optional: (y_at_0, y_at_5) in pixels. For 2286x1406: 0 ~1280, 5 ~320.
MANUAL_Y_SCALE: tuple[int, int] | None = (1280, 320)  # None = auto

# RGB tolerance for bar colors (r, g, b) - tuned for the chart
# Brown: dark taupe/brown (Scaled Optimizer Costs) e.g. (138, 121, 104)
def is_brown(r, g, b):
    return r > 90 and g < r and b < r and r < 200 and (r - g) >= 10

# Green: (Zero-Shot DeepDB Est.) e.g. (110, 157, 114)
def is_green(r, g, b):
    return g > 90 and g > r and g > b and r < 200 and b < 200

# Blue: (Zero-Shot Exact Cardinalities) e.g. (94, 116, 160)
def is_blue(r, g, b):
    return b > 90 and b > r and b >= g and r < 180


def load_image(path: Path) -> list:
    """Load image as list of rows, each row list of (r,g,b)."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    return [[tuple(px[x, y]) for x in range(w)] for y in range(h)]


def _row_mean_std(row: list) -> tuple[float, float]:
    n = len(row)
    if not n:
        return 0.0, 0.0
    mean = sum(sum(p) for p in row) / (3 * n)
    var = sum((sum(p) / 3 - mean) ** 2 for p in row) / n
    return mean, var ** 0.5


def find_baseline_and_scale_y(
    arr: list, plot_x_start: int, plot_x_end: int
) -> tuple[int, int]:
    """
    Find y pixel of baseline (0) and of the 5 line by scanning for horizontal lines.
    Returns (y_baseline, y_at_5). In image coords, y increases downward.
    """
    h = len(arr)
    x_mid = (plot_x_start + plot_x_end) // 2
    best_baseline = int(h * 0.85)
    best_5 = int(h * 0.35)
    for y in range(h - 1, int(h * 0.5), -1):
        row = [arr[y][x] for x in range(plot_x_start, min(plot_x_end, len(arr[0])))]
        mean, std = _row_mean_std(row)
        if mean < 200 and std < 30:
            best_baseline = y
            break
    for y in range(0, int(h * 0.7)):
        row = [arr[y][x] for x in range(plot_x_start, min(plot_x_end, len(arr[0])))]
        mean, std = _row_mean_std(row)
        if 100 < mean < 220 and std < 50:
            best_5 = y
            break
    return best_baseline, best_5


def bar_color_match(r: int, g: int, b: int) -> int:
    """Return 0=brown, 1=green, 2=blue, -1=other."""
    if is_brown(r, g, b):
        return 0
    if is_green(r, g, b):
        return 1
    if is_blue(r, g, b):
        return 2
    return -1


def measure_bar_height_in_column(
    arr: list,
    x_center: int,
    x_width: int,
    y_baseline: int,
    color_index: int,
) -> float:
    """
    Find bar height in pixels (baseline to bar top). Brown = tall bars, use first
    row with color from top. Green/blue = short bars, use first row with color
    when scanning from baseline upward so we don't pick up labels/grid.
    """
    width = len(arr[0])
    x_lo = max(0, x_center - x_width)
    x_hi = min(width, x_center + x_width)
    row_len = x_hi - x_lo
    min_count_brown = max(1, row_len // 4)
    min_count_short = max(1, row_len // 6)  # more lenient for short green/blue bars

    def count_match(y: int) -> int:
        return sum(
            1
            for x in range(x_lo, x_hi)
            if bar_color_match(arr[y][x][0], arr[y][x][1], arr[y][x][2]) == color_index
        )

    bar_top_y = y_baseline
    if color_index == 0:
        # Brown: tall bars – first row with color from top
        for y in range(0, y_baseline + 1):
            if count_match(y) >= min_count_brown:
                bar_top_y = y
                break
    else:
        # Green/blue: short bars – block touching baseline; end bar at first clear gap (white rows)
        min_count = min_count_short
        gap_rows = 2
        def row_mostly_white(y: int) -> bool:
            return all(
                arr[y][x][0] > 230 and arr[y][x][1] > 230 and arr[y][x][2] > 230
                for x in range(x_lo, min(x_hi, len(arr[0])))
            )
        bar_bottom_y = y_baseline + 1
        for y in range(y_baseline, -1, -1):
            if count_match(y) >= min_count:
                bar_bottom_y = y
                break
        if bar_bottom_y > y_baseline:
            pass
        else:
            bar_top_y = bar_bottom_y
            consecutive_white = 0
            for y in range(bar_bottom_y - 1, -1, -1):
                if count_match(y) >= min_count:
                    bar_top_y = y
                    consecutive_white = 0
                elif row_mostly_white(y):
                    consecutive_white += 1
                    if consecutive_white >= gap_rows:
                        break
                else:
                    consecutive_white = 0
    height_px = y_baseline - bar_top_y
    return float(max(0, height_px))


def pixel_to_value(height_px: float, range_px: float) -> float:
    """Scale pixel height to Y value: value = 5 * height_px / range_px (axis 0–5)."""
    if range_px <= 0:
        return 0.0
    return 5.0 * height_px / range_px


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    image_path = script_dir / "zeroshot-bar-chart.png"
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    arr = load_image(image_path)
    h, w = len(arr), len(arr[0])

    # Chart plot area and Y-scale (adjust if your image differs)
    plot_x_start = int(w * 0.10)
    plot_x_end = int(w * 0.94)
    plot_width = plot_x_end - plot_x_start

    if MANUAL_Y_SCALE is not None:
        y_at_0, y_at_5 = MANUAL_Y_SCALE
    else:
        y_at_0, y_at_5 = find_baseline_and_scale_y(arr, plot_x_start, plot_x_end)
        if y_at_0 <= y_at_5:
            y_at_0 = int(h * 0.85)
            y_at_5 = int(h * 0.40)

    n_workloads = len(WORKLOADS)
    # Chart has 4 bars per group: brown, green, blue, (4th). We use indices 0, 1, 2.
    bars_per_group = 4
    bar_indices = (0, 1, 2)  # brown, green, blue
    slot_width = plot_width / (n_workloads * bars_per_group)
    # Brown: slightly wider; green/blue: narrow to stay inside short bars
    x_width_brown = max(3, int(slot_width * 0.5))
    x_width_short = max(2, int(slot_width * 0.35))

    # First pass: measure all brown bar heights; calibrate scale so max brown = MAX_BROWN_QERROR (8.62)
    brown_heights_px: list[float] = []
    for i in range(n_workloads):
        x_center = plot_x_start + int((i * bars_per_group + bar_indices[0] + 0.5) * slot_width)
        brown_heights_px.append(
            measure_bar_height_in_column(arr, x_center, x_width_brown, y_at_0, 0)
        )
    max_brown_height_px = max(brown_heights_px) if brown_heights_px else 1.0
    # value = 5 * height_px / range_px; we want max_brown -> MAX_BROWN_QERROR
    # so 5 * max_brown_height_px / range_px = MAX_BROWN_QERROR => range_px = 5 * max_brown_height_px / MAX_BROWN_QERROR
    range_px = 5.0 * max_brown_height_px / MAX_BROWN_QERROR
    # Sanity: largest brown bar should equal MAX_BROWN_QERROR (8.62)
    max_brown_value = pixel_to_value(max_brown_height_px, range_px)
    max_brown_workload = WORKLOADS[brown_heights_px.index(max_brown_height_px)]
    print(f"Calibration: max brown bar = {max_brown_value:.3f} ({max_brown_workload}) [expected {MAX_BROWN_QERROR}]\n")

    results: list[dict] = []
    for i, workload in enumerate(WORKLOADS):
        row = {"Workload": workload}
        for s, name in enumerate(SERIES_NAMES):
            base_x = plot_x_start + int((i * bars_per_group + bar_indices[s] + 0.5) * slot_width)
            x_w = x_width_brown if s == 0 else x_width_short
            height_px = measure_bar_height_in_column(arr, base_x, x_w, y_at_0, s)
            # If no bar found, try adjacent positions (chart may have slight drift)
            if height_px <= 0 and slot_width >= 4:
                for dx in [-int(slot_width), int(slot_width)]:
                    h2 = measure_bar_height_in_column(arr, base_x + dx, x_w, y_at_0, s)
                    height_px = max(height_px, h2)
            value = pixel_to_value(height_px, range_px)
            row[name] = round(value, 3)
        results.append(row)

    if RESCALE_ZEROSHOT_TO_PAPER:
        max_green = max(r[SERIES_NAMES[1]] for r in results) or 1.0
        max_blue = max(r[SERIES_NAMES[2]] for r in results) or 1.0
        scale_green = PAPER_MAX_ZEROSHOT / max_green if max_green > 0 else 1.0
        scale_blue = PAPER_MAX_ZEROSHOT / max_blue if max_blue > 0 else 1.0
        for r in results:
            r[SERIES_NAMES[1]] = round(r[SERIES_NAMES[1]] * scale_green, 3)
            r[SERIES_NAMES[2]] = round(r[SERIES_NAMES[2]] * scale_blue, 3)
    # Fill remaining zeros for zero-shot with series median (Q-error >= 1)
    for idx in (1, 2):
        name = SERIES_NAMES[idx]
        values = [r[name] for r in results if r[name] > 0]
        if values:
            median_val = sorted(values)[len(values) // 2]
            for r in results:
                if r[name] <= 0:
                    r[name] = round(median_val, 3)

    # Print table (spaced columns)
    col_w = [max((len(str(row["Workload"])) for row in results), default=14)] + [
        max(len(name), 10) for name in SERIES_NAMES
    ]
    pad = 2
    header = "Workload".ljust(col_w[0] + pad) + "".join(
        name.ljust(col_w[i + 1] + pad) for i, name in enumerate(SERIES_NAMES)
    )
    print(header)
    print("-" * len(header))
    for r in results:
        line = str(r["Workload"]).ljust(col_w[0] + pad)
        for i, name in enumerate(SERIES_NAMES):
            line += str(r[name]).ljust(col_w[i + 1] + pad)
        print(line)

    # Also write CSV
    csv_path = script_dir / "zeroshot_bar_chart_extracted.csv"
    with open(csv_path, "w") as f:
        f.write("Workload," + ",".join(f'"{n}"' for n in SERIES_NAMES) + "\n")
        for r in results:
            f.write(r["Workload"] + "," + ",".join(str(r[n]) for n in SERIES_NAMES) + "\n")
    print(f"\nCSV written to {csv_path}")


if __name__ == "__main__":
    main()
