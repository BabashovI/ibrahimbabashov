# ibrahimbabashov.com

Personal site of Ibrahim Babashov — Linux sysadmin & IT engineer.
Notes, cheat sheets and experiences from real production work.

Built by hand with **plain HTML, CSS, and JavaScript** — no frameworks,
no build step, no dependencies (fonts are loaded from Google Fonts with
system fallbacks).

## Structure

```
.
├── index.html        # Landing page: hero, latest notes, toolbox, contact CTA
├── about.html        # About + certifications
├── blog.html         # Blog archive, grouped by year
├── contact.html      # Contact page
├── posts/            # 18 posts migrated from the old Blogger blog
├── css/
│   └── style.css     # Design system (dark-first, violet→cyan, light theme too)
└── js/
    └── main.js       # Theme toggle, mobile nav, reading progress, reveals
```

## Run locally

Open `index.html` in a browser, or serve the folder:

```sh
npx serve .
# or
python3 -m http.server 8000
```

## Design notes

- Dark theme by default, light theme available; saved in `localStorage`
- Reading progress bar and prev/next navigation on post pages
- Scroll-reveal animations (respects `prefers-reduced-motion`)
- No projects section — the site is a personal notebook, not a portfolio grid

## Writing a new post

1. Create `posts/my-new-note.html` (copy an existing post for the template).
2. Update the `<title>`, description, and body inside `.post-body`.
3. Add a link to it in `blog.html` (and optionally the "Latest notes"
   section on `index.html`).

## Deploying

Any static host works — GitHub Pages, Netlify, Vercel, Cloudflare Pages.
No build command needed. Point the DNS of `ibrahimbabashov.com` at your
host and you're live.
