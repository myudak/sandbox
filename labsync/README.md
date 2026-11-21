# LabSync landing page

Landing page for **LabSync**, an app for lab practicum attendance (presensi by location and QR), leave requests (izin), locked quizzes, live recap, grades and an audit log. This folder only holds the landing page; the app itself lives in its own repository.

Built with [Astro](https://astro.build), static output, no client JavaScript.

## Run

```sh
npm install
npm run dev      # http://localhost:4321
npm run build    # static site in dist/
```

## Releases

The download button and the release section read GitHub releases of this repository whose tag starts with `labsync-v` (for example `labsync-v1.0.0`), at build time. Each release needs an `.apk` asset; its `- ` bullet lines become the release notes on the page.

If GitHub can't be reached during the build, the page falls back to `FALLBACK` in `src/data/release.ts`. Keep that in step with the newest release.

## Content

- Screens in `src/assets/shots/` are captures of the app in demo mode (sample data, no real students).
- Labi the mascot and the app icon are in `public/mascot/` and `public/img/`.
- The showreel, when present, is `public/video/labsync-showreel.mp4` with `labsync-showreel.jpg` as its poster; the section is hidden without it.
