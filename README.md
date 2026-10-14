# ibrahimbabashov.com

Personal site of Ibrahim Babashov — Linux sysadmin & IT engineer.
Notes, cheat sheets and experiences from real production work.

Built by hand with **plain HTML, CSS, and JavaScript** — no frameworks and no
build step. Fonts come from Google Fonts with system fallbacks.

## Structure

```
.
├── index.html          # Landing: hero, latest notes, toolbox, contact CTA
├── about.html          # About + certifications
├── blog.html           # Blog archive, grouped by year
├── contact.html        # Contact page
├── posts/              # 18 posts migrated from the old Blogger blog
├── images/             # Localized post images (base64 extracted + downloaded)
├── css/style.css       # Design system (dark-first, light theme too)
├── js/
│   ├── theme-init.js   # Runs in <head>: theme, JS flag, watchdog
│   └── main.js         # Theme toggle, mobile nav, reading progress, reveals
├── tools/
│   ├── build_posts.py  # Regenerates posts/blog from the archived feed
│   └── blogger-feed.json  # Raw Blogger export (migration source of truth)
├── favicon.svg
├── robots.txt
└── sitemap.xml
```

## Run locally

Open `index.html` in a browser, or serve the folder:

```sh
npx serve .
# or
python3 -m http.server 8000
```

## Regenerating the blog

The 18 posts came from the old Blogger blog. `tools/build_posts.py` turns the
archived feed into clean static pages matching this site's template. It is safe
to re-run:

```sh
python3 tools/build_posts.py
```

What it does:

- parses the old markup and **strips inline styles, colours, backgrounds and
  fonts** (they were unreadable on the dark theme) and unwraps stray `<span>`
- **recovers structure**: `white-space:pre` runs become real `<pre>` code
  blocks, `●`/`○` runs become `<ul>`, numbered runs `<ol>`, prose `<p>`, and
  obvious section labels `<h3>`
- rewrites `<br>`-jammed command runs into `<pre>` blocks
- demotes headings inside post bodies (one `<h1>` per page)
- wraps wide tables in a scroll container and drops empty layout tables
- adds `alt` + `loading="lazy"` to every image
- extracts inline base64 images and downloads remote ones into `images/`
- writes the SEO head (canonical, Open Graph, Twitter, favicon)
- builds prev/next navigation, the year-grouped archive and `sitemap.xml`
- keeps the "view all N" count on the homepage in sync

> Note: a few source images (on `crybit.com` and expired Instagram CDN links)
> could not be downloaded. Those keep their original remote URLs in the markup.

## Design notes

- Dark theme by default, light theme available; saved in `localStorage`
- Reading progress bar and prev/next navigation on post pages
- Scroll-reveal animations, gated behind an `html.js` class so content stays
  visible when JavaScript is unavailable (`prefers-reduced-motion` respected)
- No projects section — this is a personal notebook, not a portfolio grid

## Writing a new post

1. Copy an existing file in `posts/` as a template.
2. Update the `<title>`, meta tags, and the `.post-body` content.
3. Add a link in `blog.html` (and optionally the "Latest notes" section on
   `index.html`).

## Deploying

Any static host works — GitHub Pages, Netlify, Vercel, Cloudflare Pages. No
build command needed. Point the DNS of `ibrahimbabashov.com` at your host.
