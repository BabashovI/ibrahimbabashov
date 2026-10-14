# ibrahimbabashov.com

Personal blog + portfolio of Ibrahim Babashov.

Built by hand with **plain HTML, CSS, and JavaScript** — no frameworks, no
build step, no dependencies.

## Structure

```
.
├── index.html        # Landing page: hero, featured projects, latest posts
├── about.html        # About page
├── projects.html     # Portfolio listing
├── blog.html         # Blog index
├── contact.html      # Contact page
├── posts/            # Individual blog posts
│   └── hello-world.html
├── css/
│   └── style.css     # All styling (light/dark theme via CSS variables)
└── js/
    └── main.js       # Theme toggle + mobile navigation
```

## Run locally

Open `index.html` in a browser, or serve the folder:

```sh
npx serve .
# or
python3 -m http.server 8000
```

## Writing a new post

1. Copy `posts/hello-world.html` to `posts/my-new-post.html`.
2. Update the `<title>`, description, and body.
3. Add a link to it in `blog.html` (and optionally the "Latest posts" section
   on `index.html`).

## Deploying

Any static host works. Common options:

- **GitHub Pages** — push to a repo, enable Pages in settings
- **Netlify / Vercel** — drag-and-drop or connect the repo, no config needed
- **Cloudflare Pages** — connect the repo, leave the build command empty

Point the DNS of `ibrahimbabashov.com` at your host of choice and you're live.

## Features

- Responsive layout with mobile navigation
- Dark / light theme toggle (saved in `localStorage`, respects system preference)
- SEO meta tags on every page
- Zero dependencies
