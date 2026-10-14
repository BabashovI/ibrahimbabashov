#!/usr/bin/env python3
"""
Regenerate the blog section of ibrahimbabashov.com from the archived Blogger
feed.

Why this exists: the 18 posts were migrated from the old Blogger blog
(ibrahimbabashov.com). This script turns the raw feed into clean, modern
static pages that match the site's own template — and it is safe to re-run.

It handles:
  * heading demotion inside post bodies (so there is only one <h1> per page)
  * wrapping wide tables in a scroll container
  * alt text + lazy loading for every image
  * extracting inline base64 images to real files in ../images/
  * downloading externally-hosted (Blogger/CDN) images into ../images/
  * SEO head (canonical, Open Graph, Twitter, favicon)
  * prev/next navigation, post labels, reading time
  * the year-grouped blog archive and sitemap.xml
  * keeping the "view all N" count on the homepage in sync

Run from anywhere:
    python3 tools/build_posts.py
"""

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from html import escape, unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "posts")
IMAGES_DIR = os.path.join(ROOT, "images")
FEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blogger-feed.json")

SITE_URL = "https://ibrahimbabashov.com"
THEME_COLOR = "#07090f"
UA = "Mozilla/5.0 (compatible; ibrahimbabashov.com migration script)"

FONT_LINKS = (
    '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '  <link href="https://fonts.googleapis.com/css2?'
    "family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600"
    '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

HEAD = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>%%TITLE%%</title>
  <meta name="description" content="%%DESC%%">
  <meta name="author" content="Ibrahim Babashov">
  <meta name="theme-color" content="%%THEME_COLOR%%">
  <link rel="canonical" href="%%CANONICAL%%">
  <meta property="og:type" content="%%OGTYPE%%">
  <meta property="og:site_name" content="ibrahimbabashov.com">
  <meta property="og:title" content="%%TITLE%%">
  <meta property="og:description" content="%%DESC%%">
  <meta property="og:url" content="%%CANONICAL%%">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="%%TITLE%%">
  <meta name="twitter:description" content="%%DESC%%">
  <link rel="icon" href="%%REL%%favicon.svg" type="image/svg+xml">
  <script src="%%REL%%js/theme-init.js"></script>
%%FONTS%%
  <link rel="stylesheet" href="%%REL%%css/style.css">
</head>
<body>
  <header class="site-header">
    <nav class="nav container">
      <a href="%%REL%%index.html" class="brand">ibrahimbabashov<span class="brand-dot">.com</span></a>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false" aria-controls="primary-nav">
        <span></span><span></span><span></span>
      </button>
      <ul class="nav-links" id="primary-nav">
%%NAV%%
        <li><a href="%%REL%%contact.html" class="btn btn-ghost btn-sm"%%CCUR%%>Contact</a></li>
        <li>
          <button class="theme-toggle" aria-label="Switch to light theme" aria-pressed="true">☀️</button>
        </li>
      </ul>
    </nav>
  </header>
"""

FOOTER = """
  <footer class="site-footer">
    <div class="container footer-inner">
      <p>© <span id="year">2026</span> Ibrahim Babashov — hand-built with HTML, CSS &amp; JS.</p>
      <div class="footer-links">
        <a href="mailto:hello@ibrahimbabashov.com">email</a>
        <a href="https://github.com/" rel="noopener" target="_blank">github</a>
        <a href="https://www.linkedin.com/" rel="noopener" target="_blank">linkedin</a>
      </div>
    </div>
  </footer>

  <script src="%%REL%%js/main.js"></script>
</body>
</html>
"""

NAV_ITEMS = [("index.html", "Home", "home"), ("about.html", "About", "about"),
             ("blog.html", "Blog", "blog")]


def page_shell(title, desc, rel, current, canonical, ogtype="website"):
    nav = "\n".join(
        '        <li><a href="{r}{h}"{cur}>{t}</a></li>'.format(
            r=rel, h=h, t=t, cur=' aria-current="page"' if active == current else "")
        for h, t, active in NAV_ITEMS
    )
    head = (
        HEAD.replace("%%TITLE%%", escape(title) + " — Ibrahim Babashov")
        .replace("%%DESC%%", desc)
        .replace("%%THEME_COLOR%%", THEME_COLOR)
        .replace("%%CANONICAL%%", canonical)
        .replace("%%OGTYPE%%", ogtype)
        .replace("%%REL%%", rel)
        .replace("%%NAV%%", nav)
        .replace("%%FONTS%%", FONT_LINKS)
        .replace("%%CCUR%%", ' aria-current="page"' if current == "contact" else "")
    )
    return head + FOOTER.replace("%%REL%%", rel)


# --------------------------------------------------------------------------
# Content cleanup
# --------------------------------------------------------------------------

def clean_content(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)

    # Drop now-dead inline alignment styles (the stylesheet handles layout).
    html = re.sub(r'\sstyle="text-align:\s*left;?"', "", html, flags=re.I)

    # Remove empty code blocks left behind by the old editor.
    html = re.sub(r"<pre[^>]*>\s*<code[^>]*>(?:\s|<span[^>]*>\s*</span>)*</code>\s*</pre>",
                  "", html, flags=re.S | re.I)
    html = re.sub(r"<pre[^>]*>\s*</pre>", "", html, flags=re.S | re.I)

    # Remove empty paragraphs.
    html = re.sub(r"<p[^>]*>\s*(?:&nbsp;)?\s*</p>", "", html, flags=re.I)

    # Only one <h1> per page: demote everything in the body by one level.
    html = re.sub(r"<h([1-6])([ >])",
                  lambda m: "<h%d%s" % (min(int(m.group(1)) + 1, 6), m.group(2)),
                  html)

    # Wide tables scroll instead of breaking the layout.
    html = re.sub(r"<table\b.*?</table>",
                  lambda m: '<div class="table-scroll">%s</div>' % m.group(0),
                  html, flags=re.S | re.I)

    # Make relative links absolute.
    html = html.replace('href="/', 'href="%s/' % SITE_URL)
    html = html.replace('src="/', 'src="%s/' % SITE_URL)
    return html


def enhance_images(html, alt_base):
    """Add alt/lazy/decoding to every <img> that lacks them."""
    counter = [0]

    def repl(m):
        tag = m.group(0)
        closing = "/>" if tag.rstrip().endswith("/>") else ">"
        inner = tag.rstrip()[: -len(closing)]
        counter[0] += 1

        if not re.search(r"\balt\s*=", inner, re.I):
            alt = alt_base if counter[0] == 1 else "%s (image %d)" % (alt_base, counter[0])
            inner += ' alt="%s"' % escape(alt, quote=True)
        if not re.search(r"\bloading\s*=", inner, re.I):
            inner += ' loading="lazy"'
        if not re.search(r"\bdecoding\s*=", inner, re.I):
            inner += ' decoding="async"'
        return inner + closing

    return re.sub(r"<img\b[^>]*>", repl, html, flags=re.I)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _ext_for(url, data):
    m = re.search(r"\.(png|jpe?g|gif|webp)(?:\?|$)", url, re.I)
    if m:
        return "jpg" if m.group(1).lower() in ("jpeg", "jpg") else m.group(1).lower()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return "png"


def localize_images(html, slug, alt_base, image_cache):
    """Extract base64 images and download remote ones into ../images/."""
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # 1) inline base64 → file
    def b64_repl(m):
        ext = "jpg" if m.group(1).lower() in ("jpeg", "jpg") else m.group(1).lower()
        data = base64.b64decode(m.group(2))
        digest = hashlib.sha1(data).hexdigest()[:10]
        name = "%s-%s.%s" % (slug, digest, ext)
        path = os.path.join(IMAGES_DIR, name)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(data)
            print("    extracted base64 -> images/%s" % name)
        return "../images/%s" % name

    html = re.sub(r"data:image/(png|jpe?g|gif);base64,([A-Za-z0-9+/=]+)",
                  b64_repl, html, flags=re.I)

    # 2) remote images → file
    urls = sorted(set(re.findall(r'src="(https?://[^"]+\.(?:png|jpe?g|gif|webp))"',
                                 html, flags=re.I)))
    for url in urls:
        if url in image_cache:
            local = image_cache[url]
        else:
            try:
                data = _fetch(url)
            except (urllib.error.URLError, OSError, ValueError) as e:
                print("    ! could not download %s (%s) — keeping remote" % (url, e))
                continue
            ext = _ext_for(url, data)
            digest = hashlib.sha1(url.encode()).hexdigest()[:10]
            name = "%s-%s.%s" % (slug, digest, ext)
            with open(os.path.join(IMAGES_DIR, name), "wb") as f:
                f.write(data)
            image_cache[url] = "../images/%s" % name
            local = image_cache[url]
            print("    downloaded -> images/%s" % name)
        html = html.replace('src="%s"' % url, 'src="%s"' % local)
        # If the same URL is also used as a link target, point it locally too.
        html = html.replace('href="%s"' % url, 'href="%s"' % local)

    return html


def text_preview(html, length=160):
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def fmt_date(iso):
    return datetime.fromisoformat(iso[:10]).strftime("%b %d, %Y")


def main():
    if not os.path.exists(FEED):
        raise SystemExit("Feed not found: %s" % FEED)

    with open(FEED) as f:
        raw = f.read()
    entries = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["feed"]["entry"]

    os.makedirs(POSTS_DIR, exist_ok=True)
    posts = []
    image_cache = {}

    for e in entries:
        title = e["title"]["$t"].strip()
        date_iso = e["published"]["$t"][:10]
        url = next(l["href"] for l in e["link"] if l.get("rel") == "alternate")
        slug = url.rstrip("/").split("/")[-1].replace(".html", "")
        labels = [c["term"] for c in e.get("category", [])]
        content_html = e.get("content", {}).get("$t", "")

        print("  %s" % slug)
        cleaned = clean_content(content_html)
        cleaned = localize_images(cleaned, slug, title, image_cache)
        cleaned = enhance_images(cleaned, title)

        desc = escape(text_preview(content_html), quote=True)
        read_mins = max(1, round(len(re.sub(r"<[^>]+>", " ", content_html)) / 1000))
        labels_html = escape(" · ".join(labels[:4])) if labels else ""
        canonical = "%s/posts/%s.html" % (SITE_URL, slug)

        head = page_shell(
            title, desc, rel="../", current="blog", canonical=canonical, ogtype="article"
        )

        labels_block = (
            '<p class="post-labels mono"><b>%s</b></p>' % labels_html if labels_html else ""
        )

        page = head + """
  <div class="progress" aria-hidden="true"><span id="progress-bar"></span></div>

  <main>
    <article class="post container">
      <header class="post-head reveal">
        <p class="post-meta mono">%%DATE%%<span class="sep">·</span>%%READ%% min read</p>
        <h1>%%H1%%</h1>
%%LABELS%%
        <p class="post-origin mono">originally published on
          <a href="%%ORIGIN%%" rel="noopener" target="_blank">ibrahimbabashov.com (Blogger)</a>
        </p>
      </header>

      <div class="post-body">
%%BODY%%
      </div>

      <nav class="post-nav" aria-label="More notes">
%%NAV%%
      </nav>

      <a class="back-link mono" href="../blog.html">← all notes</a>
    </article>
  </main>
""".replace("%%DATE%%", fmt_date(date_iso)) \
   .replace("%%READ%%", str(read_mins)) \
   .replace("%%H1%%", escape(title)) \
   .replace("%%LABELS%%", labels_block) \
   .replace("%%ORIGIN%%", url) \
   .replace("%%BODY%%", cleaned) + FOOTER.replace("%%REL%%", "../")

        with open(os.path.join(POSTS_DIR, "%s.html" % slug), "w") as f:
            f.write(page)

        posts.append({
            "title": title,
            "date_iso": date_iso,
            "date_fmt": fmt_date(date_iso),
            "slug": slug,
            "url": url,
            "labels": labels[:3],
        })

    # ---- prev / next (posts are newest-first) ----
    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i < len(posts) - 1 else None

        def block(p, direction):
            if not p:
                return "<span></span>"
            cls = " next" if direction == "Older" else ""
            return (
                '<a class="post-nav-item%s" href="%s.html">'
                '<span class="dir">%s note</span>'
                '<span class="t">%s</span></a>'
                % (cls, p["slug"], direction, escape(p["title"]))
            )

        nav_html = block(newer, "Newer") + block(older, "Older")
        fname = os.path.join(POSTS_DIR, "%s.html" % p["slug"])
        with open(fname) as f:
            page = f.read()
        with open(fname, "w") as f:
            f.write(page.replace("%%NAV%%", nav_html))

    # ---- blog.html : year-grouped archive ----
    year_blocks, rows, current_year = [], [], None
    for p in posts:
        year = p["date_iso"][:4]
        if year != current_year:
            if rows:
                year_blocks.append(_year_block(current_year, rows))
                rows = []
            current_year = year
        labels = ""
        if p["labels"]:
            labels = '<span class="note-labels"><span>%s</span></span>' % escape(
                " · ".join(p["labels"]))
        rows.append(
            '      <a class="note-row" href="posts/%s.html">\n'
            '        <span class="note-date">%s</span>\n'
            '        <span class="note-body"><span class="note-title">%s</span>%s</span>\n'
            '        <span class="note-arrow">→</span>\n'
            '      </a>' % (p["slug"], p["date_iso"], escape(p["title"]), labels)
        )
    if rows:
        year_blocks.append(_year_block(current_year, rows))

    blog = page_shell(
        "Blog",
        "All %d notes and cheat sheets by Ibrahim Babashov — Linux, networking, AWS, "
        "Salt, Docker and more." % len(posts),
        rel="./", current="blog", canonical="%s/blog.html" % SITE_URL,
    ) + """
  <main>
    <section class="page container">
      <p class="kicker">~/notes</p>
      <h1>Blog</h1>
      <p class="lead">
        Everything I learned the hard way: cheat sheets, configs and
        experiences from %d notes, 2018–2022.
      </p>

%s
    </section>
  </main>
""" % (len(posts), "\n".join(year_blocks)) + FOOTER.replace("%%REL%%", "./")

    with open(os.path.join(ROOT, "blog.html"), "w") as f:
        f.write(blog)
    print("  blog.html")

    # ---- sitemap.xml ----
    write_sitemap(posts)

    # ---- keep the homepage count in sync ----
    idx_path = os.path.join(ROOT, "index.html")
    if os.path.exists(idx_path):
        with open(idx_path) as f:
            idx = f.read()
        new_idx = re.sub(r"view all \d+", "view all %d" % len(posts), idx)
        if new_idx != idx:
            with open(idx_path, "w") as f:
                f.write(new_idx)
            print("  index.html count -> %d" % len(posts))

    print("Done: %d posts." % len(posts))


def _year_block(year, rows):
    return ('    <div class="year-block">\n'
            '      <h2 class="year-mark">%s</h2>\n%s\n    </div>' % (year, "\n".join(rows)))


def write_sitemap(posts):
    today = datetime.now().strftime("%Y-%m-%d")
    urls = [
        ("%s/" % SITE_URL, today, "1.0"),
        ("%s/about.html" % SITE_URL, today, "0.6"),
        ("%s/blog.html" % SITE_URL, today, "0.9"),
        ("%s/contact.html" % SITE_URL, today, "0.5"),
    ]
    urls += [("%s/posts/%s.html" % (SITE_URL, p["slug"]), p["date_iso"], "0.7")
             for p in posts]

    body = "\n".join(
        "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
        "    <priority>%s</priority>\n  </url>" % u
        for u in urls
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           '%s\n</urlset>\n' % body)
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write(xml)
    print("  sitemap.xml")


if __name__ == "__main__":
    main()
