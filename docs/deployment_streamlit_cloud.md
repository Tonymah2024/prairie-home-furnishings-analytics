# Deploying the dashboard to Streamlit Community Cloud

Status: **deployed 2026-10-09** at <https://prairie-home-furnishings-bi.streamlit.app> from the public repository <https://github.com/Tonymah2024/prairie-home-furnishings-analytics> (built by `scripts/build_public_repo.py`, which excludes and scrubs files naming the real retailer).

1. **Decide the public scope.** The app shows only the fictional "Prairie Home Furnishings" and synthetic data. The research notes, pilot proposal and
   demonstration guide name the retailer Furniture. If the repository will be public, leave out `docs/business_understanding.md`,
   `outputs/reports/VisiVault_Pilot_Proposal.*` and `data/external/raw/` (or keep the repository private).
2. **Create a GitHub repository** (for example `prairie-home-furnishings-analytics`). From this folder:
   `git init && git add . && git commit -m "Prairie Home Furnishings analytics demo" && git branch -M main && git remote add origin <repo-url> && git push -u origin main`.
   The SQLite database (~64 MB) is below GitHub's 100 MB file limit. `.venv/` is ignored.
3. **Create the app** at <https://share.streamlit.io> → *Create app* → choose the repository, branch `main` and main file `dashboard/app.py`.
   Under *Advanced settings* choose **Python 3.11**. No secrets are needed.
4. **Wait for the build** (installs `requirements.txt`; about 3-5 minutes), then open the app and check every page loads.
   The sidebar link to the Excel and PDF downloads works because `outputs/` is committed.
5. **Optional:** set a custom subdomain (for example `prairie-home-furnishings.streamlit.app`) in the app settings, and add the URL to
   `src/reporting/reports.py` (`DEMO_URL`), then re-run `python run_pipeline.py --from reports` so the demonstration guide shows it.

To refresh the data after code changes, run `python run_pipeline.py` locally, commit the updated `data/` and `outputs/`, and push; the app redeploys automatically.
