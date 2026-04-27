# Reserve Study Web

This folder contains a minimal Streamlit web app for running the Ridge Park reserve study from a browser.

## What It Does

- Edit core assumptions
- Maintain the component schedule in a spreadsheet-like table
- Maintain the annual assessment schedule
- Run the reserve study
- Review and download the resulting CSV outputs

The current default inputs are loaded from:

- `2026_joint_buget_maint/source_data/assumptions.csv`
- `2026_joint_buget_maint/source_data/component_list_v2.csv`
- `2026_joint_buget_maint/source_data/assessment_contributions.csv`

## Local Run

1. Create a virtual environment and install dependencies.
2. Set a shared password.
3. Start Streamlit.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export APP_PASSWORD='choose-a-strong-shared-password'
streamlit run app.py
```

For local-only testing without a password gate:

```bash
export ALLOW_NO_PASSWORD=true
streamlit run app.py
```

## Render Deployment

This repo now includes a Render Blueprint in `render.yaml`, so Render can create the web service with the right baseline settings.

### What you need

- A GitHub, GitLab, or Bitbucket repo containing this folder
- A Render account
- DNS control for `ridgeparkhoa.com` in Bluehost

### Recommended path

1. Push this project to a Git repo.
2. In Render, choose `New +` -> `Blueprint`.
3. Connect the repo that contains this `render.yaml`.
4. When prompted for `APP_PASSWORD`, enter the shared password you want for the app.
5. Let Render build and deploy the Docker service.
6. After the first deploy succeeds, add `study.ridgeparkhoa.com` as a custom domain in Render.
7. In Bluehost DNS, add the `CNAME` record that Render provides for that subdomain.

### Auto deploys

If the service stays linked to your repo, Render will automatically rebuild and redeploy when you push changes to the connected branch.

### Notes

- `DEFAULT_VARIANT` is set to `2026_joint_buget_maint` in `render.yaml`.
- `APP_PASSWORD` is marked with `sync: false`, so Render will prompt you for it during the initial Blueprint setup.
- If you later want to rotate the password, update the environment variable in the Render dashboard.

## Cloud Run Deployment

Deploy the app on a subdomain such as `study.ridgeparkhoa.com`.

```bash
gcloud run deploy reserve-study-web \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars APP_PASSWORD='choose-a-strong-shared-password',DEFAULT_VARIANT='2026_joint_buget_maint'
```

After deployment:

1. Map a custom domain such as `study.ridgeparkhoa.com`.
2. Add a link to that subdomain from a password-protected page on `ridgeparkhoa.com`.
3. If you want stronger protection than a shared password, place the app behind Cloudflare Access or another identity layer.

## Main Files

- `app.py`: Streamlit user interface and password gate
- `reserve_plots.py`: matplotlib plots shown in the app's `Plots` tab
- `reserve_study_v3_3.py`: reserve-study engine plus reusable `run_reserve_study(...)`
- `requirements.txt`: Python dependencies
- `Dockerfile`: container for Cloud Run or another container host
- `render.yaml`: Render Blueprint for one-click repo-based deployment
