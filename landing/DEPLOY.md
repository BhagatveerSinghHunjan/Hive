# Deploy HIVE landing + download (Vercel)

The marketing site lives in `landing/`. The Mac app zip is ~94MB, so host the
**binary on GitHub Releases** and point the landing page download button at it.
Vercel serves the page only.

## 1. Build the Mac download

```bash
cd desktop
npm install
npm run dist
# → desktop/release/HIVE-mac.zip
```

## 2. Upload the zip to GitHub Releases

1. Push this repo to GitHub (if it isn’t already).
2. Open **Releases → Draft a new release**.
3. Tag: `v0.1.0` (or next version).
4. Upload `desktop/release/HIVE-mac.zip`.
5. Publish the release.
6. Copy the asset URL, e.g.  
   `https://github.com/<you>/<repo>/releases/download/v0.1.0/HIVE-mac.zip`

## 3. Point the landing page at that URL

Edit `landing/index.html` and set:

```html
<meta name="hive-download-url" content="https://github.com/<you>/<repo>/releases/download/v0.1.0/HIVE-mac.zip" />
```

## 4. Deploy the landing page to Vercel

### Option A — Vercel website (easiest)

1. Go to [vercel.com](https://vercel.com) → **Add New Project**.
2. Import your GitHub repo.
3. Set **Root Directory** to `landing`.
4. Framework Preset: **Other**.
5. Build Command: leave empty. Output: leave empty (static files).
6. Deploy.

### Option B — Vercel CLI

```bash
npm i -g vercel
cd landing
vercel login
vercel
# Production:
vercel --prod
```

When prompted, use root `landing`, no build command.

## 5. Verify

1. Open your `*.vercel.app` URL.
2. Click **Download for Mac** — it should fetch the GitHub Release zip.
3. Unzip → open **HIVE.app** (right-click → Open the first time if Gatekeeper blocks unsigned apps).

## Optional: host the zip on Vercel too

Only if the zip stays under your plan’s upload limit (often tight on Hobby):

```bash
cd desktop && npm run publish-landing
# copies zip → landing/downloads/HIVE-mac.zip
```

Leave `hive-download-url` empty so the button uses `/downloads/HIVE-mac.zip`.
Prefer GitHub Releases for reliability.
