# amin-tabrizian.github.io

Personal site. Plain HTML and one stylesheet, no build step. GitHub Pages serves the
`master` branch as is (`.nojekyll` turns Jekyll off).

- `index.html`: everything on the home page (bio, news, papers, teaching, talks, service)
- `calendar/`: booking page
- `style.css`: all styling
- `images/papers/`: paper thumbnails, 480x320 (3:2), `.webp`
- `files/CV.pdf`: CV

Old URLs (`/news/`, `/publications/`, `/teaching/`, `/talks/`, `/contact/`, `/about/`, `/cv/`)
are small redirect pages.

## Adding a paper

Copy an `<article class="pub">` block in `index.html`. For a figure that changes on hover, add a
second `<img class="alt">` inside the `.thumb` link. A short looping clip also works:
`<video src="images/papers/clip.mp4" autoplay muted loop playsinline></video>`.

## Calendar

`calendar/` shows busy times from two iCal feeds. `.github/workflows/busy.yml` runs
`scripts/build_busy.py` every 20 minutes, merges the feeds into busy blocks (start and end only,
no titles), and commits `calendar/busy.json` when it changes. The feed links live in the repo
secrets `GWU_ICS_URL` and `CIGNUS_ICS_URL`.

## Preview locally

    python3 -m http.server 8000

then open http://localhost:8000.
