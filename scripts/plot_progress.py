"""Render the progress charts shown in the README (light and dark variants)."""

from __future__ import annotations

import collections
import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from common import ROOT, load_config, load_papers  # noqa: E402

ASSETS = ROOT / "assets"

THEMES = {
    "light": {
        "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
    },
    "dark": {
        "surface": "#1a1a19", "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500"],
    },
}


def _style(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def _title(ax, t, title, subtitle):
    # Offsets in points so spacing is identical regardless of figure height.
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 26), textcoords="offset points",
                fontsize=12, fontweight="bold", color=t["ink"], va="bottom")
    ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction", xytext=(0, 12), textcoords="offset points",
                fontsize=9, color=t["ink2"], va="bottom")


def timeline(papers, config, t, out):
    groups = config["plot_groups"]
    cat_to_group = {c: i for i, g in enumerate(groups) for c in g["categories"]}
    years = sorted({int(p["date"][:4]) for p in papers})
    years = list(range(years[0], years[-1] + 1))
    counts = [[0] * len(years) for _ in groups]
    for p in papers:
        counts[cat_to_group.get(p["category"], 0)][years.index(int(p["date"][:4]))] += 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.45, 1]})
    fig.patch.set_facecolor(t["surface"])

    # Stacked bars: papers per year by research area.
    bottoms = [0] * len(years)
    for gi, g in enumerate(groups):
        ax1.bar(years, counts[gi], bottom=bottoms, width=0.72, color=t["series"][gi], label=g["name"],
                edgecolor=t["surface"], linewidth=1.5)
        bottoms = [b + c for b, c in zip(bottoms, counts[gi])]
    for x, total in zip(years, bottoms):
        if total:
            ax1.text(x, total + max(bottoms) * 0.015, str(total), ha="center", va="bottom", fontsize=8,
                     color=t["ink2"])
    _style(ax1, t)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
    step = 1 if len(years) <= 12 else 2
    ax1.set_xticks(years[::-1][::step][::-1])
    ax1.set_xticklabels([str(y) for y in years[::-1][::step][::-1]], rotation=0)
    current = dt.date.today().year
    _title(ax1, t, "Papers per year", f"By research area ({current} is year to date)")
    leg = ax1.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=t["ink2"], handlelength=1,
                     handleheight=1)
    for h in leg.legend_handles:
        h.set_edgecolor("none")

    # Cumulative total over time.
    monthly = collections.Counter(p["date"][:7] for p in papers)
    start = dt.date(years[0], 1, 1)
    end = dt.date.today().replace(day=1)
    xs, ys, running, d = [], [], 0, start
    while d <= end:
        running += monthly.get(d.strftime("%Y-%m"), 0)
        xs.append(d)
        ys.append(running)
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    ax2.plot(xs, ys, color=t["series"][0], linewidth=2, solid_capstyle="round")
    ax2.fill_between(xs, ys, color=t["series"][0], alpha=0.12, linewidth=0)
    ax2.plot([xs[-1]], [ys[-1]], marker="o", markersize=6, color=t["series"][0],
             markeredgecolor=t["surface"], markeredgewidth=2)
    ax2.annotate(f"{ys[-1]} total", (xs[-1], ys[-1]), xytext=(-8, 0), textcoords="offset points",
                 ha="right", va="center", fontsize=9, color=t["ink"], fontweight="bold")
    _style(ax2, t)
    ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
    _title(ax2, t, "Cumulative papers", "Everything in the list, by first arXiv / publication date")

    fig.tight_layout(w_pad=3)
    fig.savefig(out, format="svg", facecolor=t["surface"], metadata={"Date": None}, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)


def by_category(papers, config, t, out):
    counts = collections.Counter(p["category"] for p in papers)
    cats = [c for c in config["categories"]]
    cats.sort(key=lambda c: counts.get(c["id"], 0))
    labels = [c["title"] for c in cats]
    values = [counts.get(c["id"], 0) for c in cats]

    fig, ax = plt.subplots(figsize=(12, 0.36 * len(cats) + 1.2))
    fig.patch.set_facecolor(t["surface"])
    ax.barh(labels, values, height=0.62, color=t["series"][0], edgecolor=t["surface"], linewidth=1.5)
    for y, v in enumerate(values):
        ax.text(v + max(values) * 0.01, y, str(v), va="center", fontsize=8.5, color=t["ink2"])
    _style(ax, t)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(t["axis"])
    ax.tick_params(axis="y", colors=t["ink2"], labelsize=9.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _title(ax, t, "Papers per category", "Each paper is filed under one primary category")
    fig.tight_layout()
    fig.savefig(out, format="svg", facecolor=t["surface"], metadata={"Date": None}, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)


def main():
    papers = load_papers()
    config = load_config()
    if not papers:
        return
    ASSETS.mkdir(exist_ok=True)
    plt.rcParams["svg.hashsalt"] = "awesome-looped-transformers"
    for name, theme in THEMES.items():
        timeline(papers, config, theme, ASSETS / f"stats-timeline-{name}.svg")
        by_category(papers, config, theme, ASSETS / f"stats-categories-{name}.svg")


if __name__ == "__main__":
    main()
