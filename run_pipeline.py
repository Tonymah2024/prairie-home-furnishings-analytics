"""One-command, reproducible pipeline for the Prairie Home Furnishings analytics demonstration (VisiVault Analytics Ltd.).

    python run_pipeline.py                 # full rebuild from the saved public snapshots (~3 min)
    python run_pipeline.py --from finance  # resume from a step

Steps: research -> synthetic -> database -> analytics -> models -> finance -> recommendations -> reports -> docs
"""
import argparse
import sys
import time

STEPS = ["research", "synthetic", "database", "analytics", "models", "finance", "recommendations", "reports", "docs"]


def run(step):
    if step == "research":
        from src.research import build_catalogue; build_catalogue.build()
    elif step == "synthetic":
        from src.generate import synthetic; synthetic.main()
    elif step == "database":
        from src.engineering import load_db
        r = load_db.run()
        bad = r["checks"][r["checks"].violations > 0]
        if len(bad) or r["fk"]:
            raise SystemExit(f"Database validation failed:\n{bad}")
    elif step == "analytics":
        from src.analysis import analytics; analytics.run()
    elif step == "models":
        from src.models import run_models; run_models.run()
    elif step == "finance":
        from src.finance import run as finance; print("   ", finance.run())
    elif step == "recommendations":
        from src.analysis import recommendations; recommendations.build()
    elif step == "reports":
        from src.reporting import reports; print("   ", reports.run())
    elif step == "docs":
        from src.reporting import docs; docs.run()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="research", choices=STEPS)
    a = ap.parse_args()
    t0 = time.time()
    for s in STEPS[STEPS.index(a.start):]:
        t = time.time()
        print(f"[{s}] ...", flush=True)
        run(s)
        print(f"[{s}] done in {time.time() - t:.1f}s", flush=True)
    print(f"Pipeline complete in {time.time() - t0:.0f}s", file=sys.stderr)
