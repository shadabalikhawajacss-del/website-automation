# Deployment Architecture

## Browser choice

The automation browser is **Playwright Chromium**.

Reasons:

- RT BDI requires real login/session behavior.
- Reports are `.fwx` pages with dynamic controls.
- Filters use Select2-style dropdowns.
- Exports use a mix of Raw Excel, grid export, and report-specific buttons.
- A saved Playwright storage state lets the backend reuse an authenticated RT BDI
  browser session without putting credentials into frontend code.

## Recommended production shape

```text
User browser
  -> Static chatbot UI: Vercel, CloudFront/S3, or any static host
  -> Backend API: AWS container service running Python + Playwright Chromium
  -> RT BDI live website
```

The frontend is static. The backend is not static because it must:

- hold RT BDI credentials/storage state securely;
- hold `OPENAI_API_KEY` securely;
- run Chromium;
- download and parse live RT BDI exports;
- keep conversation memory/session state.

## Frontend hosting options

Good choices:

- Vercel static site
- AWS S3 + CloudFront
- Netlify static site

The static site lives in `web/`.

Set the backend URL in the page before loading `app.js`, or store it in browser
local storage as `rtbdiApiBase`.

## Backend hosting options

Best choices:

- AWS ECS Fargate container
- AWS App Runner container
- EC2 systemd service

Avoid pure serverless for the live automation path unless the runtime supports
Playwright Chromium reliably and has enough execution time for long exports.

## Required backend environment variables

```bash
RTBDI_BASE_URL=https://www.myrtpos.com/newbdi/index.fwx
RTBDI_USERNAME=...
RTBDI_PASSWORD=...
RTBDI_STORAGE_STATE=/secure/path/storage-state.json
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
RTBDI_MEMORY_DIR=/data/rtbdi-memory
```

For production, prefer `RTBDI_STORAGE_STATE` or a secrets manager instead of
typing the RT BDI password into every runtime environment.

## Running locally

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
uvicorn rtbdi_assistant.api:app --host 0.0.0.0 --port 8000
```

Open `web/index.html` and point it to the API base URL.
