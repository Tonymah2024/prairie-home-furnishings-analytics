"""Shared HTML -> PDF helpers (headless Chrome) and VisiVault report styling."""
import base64
import html
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from src.config import BRAND, CHARTS

CHROME_CANDIDATES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                     shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or ""]


def money(v, d=0):
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v / 1e6:,.2f}M" if v >= 1e6 else f"{s}${v:,.{d}f}"


def pct(v, d=0):
    return f"{v * 100:.{d}f}%"


def img(name, caption="", width="100%"):
    p = CHARTS / f"{name}.png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    cap = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
    return f"<figure><img src='data:image/png;base64,{b64}' style='width:{width}'/>{cap}</figure>"


def tbl(df: pd.DataFrame, cls="", fmt=None):
    fmt = fmt or {}
    h = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            v = fmt[c](v) if c in fmt and pd.notna(v) else ("" if pd.isna(v) else v)
            cells.append(f"<td>{v}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table class='{cls}'><thead><tr>{h}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


CSS = f"""
@page {{ size: Letter; margin: 17mm 15mm 18mm 15mm;
  @bottom-left {{ content: "VisiVault Analytics Ltd.  |  Prairie Home Furnishings (fictional)  |  SYNTHETIC DEMONSTRATION DATA - not actual company records"; font: 7.5pt Helvetica, Arial; color: {BRAND['accent']}; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font: 7.5pt Helvetica, Arial; color: #888; }} }}
@page cover {{ margin: 0; @bottom-left {{ content: none }} @bottom-right {{ content: none }} }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 9.6pt; line-height: 1.45; color: {BRAND['navy']}; margin: 0; }}
h1 {{ font-size: 20pt; margin: 0 0 6px; color: {BRAND['navy']}; }}
h2 {{ font-size: 14pt; color: {BRAND['brand_dark']}; border-bottom: 2px solid {BRAND['brand']}; padding-bottom: 3px; margin: 18px 0 8px; break-after: avoid; }}
h3 {{ font-size: 11pt; color: {BRAND['navy']}; margin: 12px 0 4px; break-after: avoid; }}
p {{ margin: 4px 0 7px; }}
ul {{ margin: 3px 0 8px 0; padding-left: 18px; }} li {{ margin: 2px 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 8.2pt; break-inside: auto; }}
th {{ background: {BRAND['navy']}; color: #fff; text-align: left; padding: 4px 6px; font-weight: 600; }}
td {{ border-bottom: 1px solid #e3e2dd; padding: 3.5px 6px; vertical-align: top; }}
tr {{ break-inside: avoid; }}
tbody tr:nth-child(even) td {{ background: #f7f7f5; }}
figure {{ margin: 6px 0 10px; break-inside: avoid; }} figure img {{ border: 1px solid #ecebe7; border-radius: 4px; }}
figcaption {{ font-size: 8pt; color: {BRAND['muted']}; margin-top: 2px; }}
.callout {{ background: {BRAND['brand_light']}; border-left: 4px solid {BRAND['brand']}; padding: 8px 12px; margin: 8px 0; break-inside: avoid; }}
.warn {{ background: #fff4e5; border-left: 4px solid #d97706; padding: 8px 12px; margin: 8px 0; break-inside: avoid; font-size: 8.8pt; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 0 12px; }}
.kpi {{ border: 1px solid #e3e2dd; border-radius: 8px; padding: 8px 10px; break-inside: avoid; }}
.kpi .l {{ font-size: 7.4pt; text-transform: uppercase; letter-spacing: .04em; color: {BRAND['muted']}; }}
.kpi .v {{ font-size: 15pt; font-weight: 700; color: {BRAND['brand_dark']}; }}
.kpi .s {{ font-size: 7.6pt; color: {BRAND['muted']}; }}
.tag {{ display:inline-block; font-size:7pt; font-weight:700; padding:1px 6px; border-radius: 8px; }}
.tag.v {{ background:#e3f5f2; color:{BRAND['teal']}; }} .tag.s {{ background:#efeaf9; color:{BRAND['accent']}; }} .tag.a {{ background:#fff4e5; color:#b45309; }}
.pb {{ break-before: page; }}
.two {{ display:block; }}
.cover {{ page: cover; height: 279mm; background: linear-gradient(160deg, {BRAND['navy']} 0%, {BRAND['brand_dark']} 70%, {BRAND['brand']} 100%); color: #fff; padding: 34mm 22mm; position: relative; }}
.cover h1 {{ color:#fff; font-size: 28pt; line-height: 1.15; margin-bottom: 14px; }}
.cover .sub {{ font-size: 13pt; opacity: .9; }}
.cover .meta {{ position:absolute; bottom: 30mm; left: 22mm; right: 22mm; font-size: 10pt; opacity:.92; }}
.cover .badge {{ display:inline-block; background:#fff4e5; color:#7a4a00; font-weight:700; padding:6px 12px; border-radius:6px; font-size:9.5pt; margin-top:22px; }}
.brandmark {{ font-weight: 800; letter-spacing: .02em; font-size: 12pt; }}
.small {{ font-size: 8pt; color: {BRAND['muted']}; }}
.toc li {{ margin: 3px 0; }}
"""


def page(title, body):
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"


def render_pdf(html_path: Path, pdf_path: Path):
    chrome = next((c for c in CHROME_CANDIDATES if c and Path(c).exists()), None)
    if not chrome:
        print("WARNING: no Chrome/Edge found - HTML written, PDF skipped:", html_path)
        return False
    import tempfile
    if pdf_path.exists():
        pdf_path.unlink()
    with tempfile.TemporaryDirectory(prefix="phf_chrome_") as prof:      # isolated profile so parallel/stale Chrome sessions cannot block rendering
        proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-sandbox", "--no-first-run", "--disable-extensions",
                                 f"--user-data-dir={prof}", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        for _ in range(240):                                             # Chrome can linger after writing the PDF: stop once the file is complete
            if proc.poll() is not None:
                break
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                time.sleep(2)
                break
            time.sleep(1)
        if proc.poll() is None:
            proc.kill()
    return pdf_path.exists()


