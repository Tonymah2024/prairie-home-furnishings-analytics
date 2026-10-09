"""Shared VisiVault chart styling (matplotlib) with a mandatory synthetic-data footer."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from src.config import BRAND, CHARTS, SERIES

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10, "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9.5, "axes.labelcolor": BRAND["muted"], "axes.edgecolor": "#d6d4cf",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#ebeae6",
    "grid.linewidth": 0.8, "axes.axisbelow": True, "xtick.color": BRAND["muted"], "ytick.color": BRAND["muted"],
    "legend.frameon": False, "legend.fontsize": 8.5, "figure.dpi": 110, "savefig.dpi": 160,
    "axes.prop_cycle": matplotlib.cycler(color=SERIES), "figure.facecolor": "white",
})

FOOTER = "SYNTHETIC DEMONSTRATION DATA  |  Prairie Home Furnishings (fictional)  |  VisiVault Analytics Ltd."


def fig(w=9, h=4.6, nrows=1, ncols=1, **kw):
    f, ax = plt.subplots(nrows, ncols, figsize=(w, h), **kw)
    return f, ax


def save(f, name: str, subtitle: str | None = None):
    if subtitle:
        f.text(0.012, 0.015, subtitle, fontsize=7.5, color=BRAND["subtle"], ha="left")
    f.text(0.988, 0.015, FOOTER, fontsize=7, color=BRAND["accent"], ha="right", alpha=0.85)
    f.tight_layout(rect=(0, 0.04, 1, 1))
    path = CHARTS / f"{name}.png"
    f.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(f)
    return path


def cad(ax, axis="y", k=False):
    if k:
        fmt = mtick.FuncFormatter(lambda v, _: ("-" if v < 0 else "") + (f"${abs(v) / 1e6:.1f}M" if abs(v) >= 1e6 else f"${abs(v) / 1e3:,.0f}K"))
    else:
        fmt = mtick.FuncFormatter(lambda v, _: ("-" if v < 0 else "") + f"${abs(v):,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def pct(ax, axis="y", decimals=0):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(mtick.PercentFormatter(decimals=decimals))
