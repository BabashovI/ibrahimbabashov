#!/usr/bin/env python3
"""
Regenerate the blog section of ibrahimbabashov.com from the archived Blogger
feed.

Why this exists: the 18 posts were migrated from the old Blogger blog
(ibrahimbabashov.com). Blogger stored them as styled <div> "lines" with
hard-coded colours, backgrounds, white-space:pre and ● bullets — which lose
their structure and become unreadable on this site's dark theme. This script
parses that markup into a tree and rebuilds it as clean, consistent HTML that
matches the design system. It is safe to re-run.

Normalization performed on every post body:
  * drop inline styles / colours / backgrounds / fonts (readability + theme)
  * unwrap meaningless <span>, <font>, <small> wrappers
  * recover code blocks (white-space:pre runs) as real <pre>
  * turn ●/○ runs into <ul>, numbered runs into <ol>, prose lines into <p>
  * convert <br>-jammed command runs inside paragraphs into <pre>
  * keep one <h1> per page (body headings are demoted)
  * wrap wide tables in a scroll container
  * alt text + lazy loading on every image
  * extract inline base64 images and download remote ones into ../images/

It also writes the SEO head, the year-grouped archive, sitemap.xml and keeps
the homepage "view all N" count in sync.

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
from html.parser import HTMLParser

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


# ==========================================================================
# HTML tree + content normalization
# ==========================================================================

VOID = {"br", "img", "hr", "input", "meta", "link", "source", "area", "base",
        "col", "embed", "param", "track", "wbr"}

BLOCK = {"div", "p", "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr",
         "td", "th", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
         "section", "article", "figure", "figcaption", "hr", "dl", "dt", "dd",
         "center", "form", "main", "header", "footer", "aside", "nav"}

INLINE_KEEP = {"a", "b", "strong", "i", "em", "u", "code", "sub", "sup",
               "mark", "abbr", "q", "cite", "time", "kbd", "samp", "var"}

UNWRAP = {"span", "font", "small", "big", "tt", "strike", "s", "label"}

CODE_TOKENS = (
    "sudo", "docker", "podman", "git", "salt", "salt-call", "systemctl", "mkdir",
    "mount", "umount", "yum", "dnf", "apt", "apt-get", "iptables", "virsh",
    "qemu", "virt-install", "chmod", "chown", "ls", "cd", "cp", "mv", "rm",
    "cat", "echo", "grep", "awk", "sed", "find", "tar", "ssh", "scp", "rsync",
    "vim", "vi", "nano", "kill", "ps", "top", "df", "free", "fdisk", "mkfs",
    "ln", "touch", "wc", "jobs", "export", "source", "curl", "wget", "python",
    "php", "kubectl", "rpm", "service", "hostnamectl", "firewall-cmd",
    "setsebool", "getenforce", "restorecon", "parted", "lvcreate", "lvreduce",
    "vgextend", "passwd", "useradd", "usermod", "groupadd", "visudo", "crontab",
    "journalctl", "dmesg", "uname", "lscpu", "ifconfig", "ip", "route",
    "netstat", "nmap", "dig", "nslookup", "ping", "traceroute", "wget",
)


class El:
    __slots__ = ("tag", "attrs", "kids")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.kids = []


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = El("#root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = El(tag, attrs)
        self.stack[-1].kids.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(El(tag, attrs))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].kids.append(data)

    def handle_entityref(self, name):
        self.stack[-1].kids.append(unescape("&%s;" % name))

    def handle_charref(self, name):
        self.stack[-1].kids.append(unescape("&#%s;" % name))


def _style(el):
    return el.attrs.get("style", "") or ""


def _is_ws_pre(el):
    s = _style(el).replace(" ", "").lower()
    return "white-space" in s and "pre" in s


def _contains_blockish(el):
    for c in el.kids:
        if isinstance(c, El):
            if c.tag in BLOCK or c.tag in ("img", "table", "pre"):
                return True
            if _contains_blockish(c):
                return True
    return False


def _is_leaf_line(el):
    return el.tag == "div" and not _contains_blockish(el)


def _text_with_breaks(nodes):
    """Plain text, with a newline at each block/line boundary. Preserves
    indentation (nbsp -> space). Used for code blocks."""
    parts = []

    def rec(ns):
        for c in ns:
            if isinstance(c, str):
                parts.append(c.replace("\xa0", " "))
            elif c.tag == "br":
                parts.append("\n")
            elif c.tag in ("div", "p", "li", "tr", "section", "blockquote"):
                rec(c.kids)
                parts.append("\n")
            else:
                rec(c.kids)

    rec(nodes)
    text = "".join(parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def _code_line(text):
    t = text.strip()
    if not t:
        return False
    if t.startswith(("$", "#", ">", "%", "./", "~/", ":")):
        return True
    # Dockerfile / uppercase directives: FROM, EXPOSE, RUN, COPY, WORKDIR...
    if re.match(r"^[A-Z][A-Z0-9_]{1,}\b", t) and not t.endswith(":"):
        return True

    low = t.lower()
    sentence = t.endswith((".", "!", "?", ":"))
    first = low.split()[0] if low.split() else ""
    token_hit = first in CODE_TOKENS
    flag = bool(re.search(r"(^|\s)-{1,2}[a-zA-Z]", t))
    shell = bool(re.search(r"(/\w+/|://|\|\s|>\s|\w=\S)", t))

    if token_hit and not sentence:
        return True
    if token_hit and (flag or shell):
        return True
    if flag and not sentence:
        return True
    if shell and not sentence:
        return True
    return False


def _is_bullet(text):
    return bool(re.match(r"^[●○▪•·*\-–]\s*", text.strip()))


def _is_numbered(text):
    return bool(re.match(r"^\d+[.)]\s+", text.strip()))


def _is_title(text):
    t = text.strip()
    if not t or len(t) > 48 or t.endswith((".", "!", "?", ",", ":", ";")):
        return False
    words = t.split()
    if not (2 <= len(words) <= 6):
        return False
    return all(w[:1].isupper() for w in words if w[:1].isalpha())


def _is_label(text):
    """A short, capitalised label ending in a colon — a section marker such
    as 'Bash:' or 'Salt master:'."""
    t = text.strip()
    if not t.endswith(":"):
        return False
    words = t[:-1].split()
    if not (1 <= len(words) <= 3):
        return False
    return words[0][:1].isupper()


def _pre(nodes):
    return "<pre>%s</pre>" % escape(_text_with_breaks(nodes), quote=False)


class Renderer:
    def __init__(self):
        self.out = []

    # -- inline ----------------------------------------------------------
    def inline(self, el):
        if el.tag == "a":
            href = el.attrs.get("href", "")
            inner = self.children(el.kids, False)
            if not href:
                return inner
            attrs = ' href="%s"' % escape(href, quote=True)
            if href.startswith(("http://", "https://")) and "ibrahimbabashov" not in href:
                attrs += ' rel="noopener" target="_blank"'
            return "<a%s>%s</a>" % (attrs, inner)
        if el.tag == "img":
            return self.image(el)
        if el.tag == "br":
            return "<br>"
        inner = self.children(el.kids, False)
        if el.tag == "code":
            return "<code>%s</code>" % inner
        return "<%s>%s</%s>" % (el.tag, inner, el.tag)

    def image(self, el):
        a = el.attrs
        src = a.get("src", "")
        if not src:
            return ""
        parts = ['src="%s"' % escape(src, quote=True)]
        if a.get("alt") is not None:
            parts.append('alt="%s"' % escape(a.get("alt", ""), quote=True))
        for k in ("width", "height"):
            v = a.get(k, "")
            if v.isdigit():
                parts.append('%s="%s"' % (k, v))
        return "<img %s>" % " ".join(parts)

    # -- block -----------------------------------------------------------
    def block(self, el):
        tag = el.tag
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return "<%s>%s</%s>" % (tag, self.children(el.kids, False), tag)

        if tag == "p":
            inner = self.children(el.kids, False)
            if not inner.strip():
                return ""
            lines = [re.sub(r"<[^>]+>", "", x).strip()
                     for x in inner.split("<br>")]
            ne = [x for x in lines if x]
            if (len(ne) >= 3 and "<img" not in inner and "<a " not in inner
                    and sum(_code_line(x) for x in ne) / len(ne) >= 0.5):
                return "<pre>%s</pre>" % "\n".join(ne)
            return "<p>%s</p>" % inner

        if tag in ("ul", "ol"):
            items = "".join(self.block(li) for li in el.kids
                            if isinstance(li, El) and li.tag == "li")
            if not items:
                return self.children(el.kids, True)
            return "<%s>%s</%s>" % (tag, items, tag)

        if tag == "li":
            return "<li>%s</li>" % self.children(el.kids, False)

        if tag == "table":
            inner = self.children(el.kids, True)
            if not re.sub(r"<[^>]+>", "", inner).strip() and "<img" not in inner:
                return ""  # empty layout table left by the old editor
            return '<div class="table-scroll"><table>%s</table></div>' % inner

        if tag in ("thead", "tbody", "tfoot"):
            return "<%s>%s</%s>" % (tag, self.children(el.kids, True), tag)

        if tag == "tr":
            return "<tr>%s</tr>" % self.children(el.kids, True)

        if tag in ("td", "th"):
            extra = ""
            for k in ("colspan", "rowspan"):
                if el.attrs.get(k, "").isdigit():
                    extra += ' %s="%s"' % (k, el.attrs[k])
            return "<%s%s>%s</%s>" % (tag, extra, self.children(el.kids, False), tag)

        if tag == "blockquote":
            return "<blockquote>%s</blockquote>" % self.children(el.kids, True)

        if tag == "hr":
            return "<hr>"

        # transparent containers
        return self.children(el.kids, True)

    # -- runs & children -------------------------------------------------
    def _kind(self, text):
        t = text.strip()
        if not t:
            return "skip"
        if _is_bullet(t):
            return "bullet"
        if _is_numbered(t):
            return "num"
        if _code_line(t):
            return "code"
        return "prose"

    def _emit(self, items):
        """items: list of (rendered_inline, plain_text). Classify each line,
        then coalesce consecutive same-kind lines into <pre>/<ul>/<ol>/<p>."""
        items = [(r, p) for (r, p) in items if p.strip()]
        if not items:
            return ""
        kinds = [self._kind(p) for _, p in items]
        # a non-title, non-label line right after a bullet is a wrapped
        # continuation of that bullet
        for idx in range(1, len(items)):
            if kinds[idx] != "prose" or kinds[idx - 1] != "bullet":
                continue
            nxt = items[idx][1].strip()
            if nxt[:1].islower() or (not _is_title(nxt) and not nxt.endswith(":")):
                kinds[idx] = "bullet"

        out = []
        i, n = 0, len(kinds)
        while i < n:
            kind = kinds[i]
            group = []
            j = i
            while j < n and kinds[j] == kind:
                group.append(items[j])
                j += 1
            if kind == "code":
                out.append("<pre>%s</pre>" % escape(
                    "\n".join(p.strip("\n") for _, p in group), quote=False))
            elif kind == "bullet":
                lis = [re.sub(r"^([●○▪•·*\-–])\s*", "", r, count=1).strip()
                       for r, _ in group]
                out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % x for x in lis))
            elif kind == "num":
                lis = [re.sub(r"^\d+[.)]\s+", "", r, count=1).strip()
                       for r, _ in group]
                out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % x for x in lis))
            else:
                for r, p in group:
                    if not r.strip():
                        continue
                    if _is_title(p) or _is_label(p):
                        out.append("<h3>%s</h3>" % r.strip())
                    else:
                        out.append("<p>%s</p>" % r.strip())
            i = j
        return "".join(out)

    def classify_run(self, run):
        items = [(self.children(el.kids, False), _text_with_breaks([el]).strip())
                 for el in run]
        return self._emit(items)

    def wrap_inline(self, s, auto_wrap):
        if not s.strip():
            return ""
        if not auto_wrap:
            return s
        if "<img" in s:
            return "<p>%s</p>" % s
        if "<br>" in s:
            items = [(ln.strip(), re.sub(r"<[^>]+>", "", ln).strip())
                     for ln in s.split("<br>")]
            return self._emit(items)
        return "<p>%s</p>" % s

    def children(self, kids, auto_wrap):
        out = []
        buf = []

        def flush():
            if buf:
                out.append(self.wrap_inline("".join(buf), auto_wrap))
                buf.clear()

        i = 0
        n = len(kids)
        while i < n:
            k = kids[i]
            if isinstance(k, str):
                if not k.strip():
                    if "\n" not in k:
                        buf.append(" ")
                else:
                    buf.append(re.sub(r"\s+", " ", k.replace("\xa0", " ")))
                i += 1
                continue
            tag = k.tag
            if tag in ("script", "style"):
                i += 1
                continue
            if tag == "br":
                buf.append("<br>")
                i += 1
                continue
            if tag in UNWRAP:
                buf.append(self.children(k.kids, False))
                i += 1
                continue
            if tag == "pre":
                flush()
                out.append(_pre(k.kids))
                i += 1
                continue
            if tag == "div" and _is_leaf_line(k):
                run = [k]
                j = i + 1
                while j < n:
                    nxt = kids[j]
                    if isinstance(nxt, str) and not nxt.strip():
                        j += 1
                        continue
                    if isinstance(nxt, El) and nxt.tag == "br":
                        j += 1
                        continue
                    if isinstance(nxt, El) and nxt.tag == "div" and _is_leaf_line(nxt):
                        run.append(nxt)
                        j += 1
                        continue
                    break
                flush()
                out.append(self.classify_run(run))
                i = j
                continue
            if tag == "img":
                flush()
                out.append(self.image(k))
                i += 1
                continue
            if tag == "hr":
                flush()
                out.append("<hr>")
                i += 1
                continue
            if tag in INLINE_KEEP:
                buf.append(self.inline(k))
                i += 1
                continue
            if tag in BLOCK:
                flush()
                out.append(self.block(k))
                i += 1
                continue
            buf.append(self.children(k.kids, False))
            i += 1
        flush()
        return "".join(x for x in out if x)


def pre_clean(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"<a\b[^>]*name=[\"']more[\"'][^>]*>\s*</a>", "", html, flags=re.I)
    html = re.sub(r"<a\b[^>]*name=\"more\"[^>]*>", "", html, flags=re.I)
    return html


def normalize_body(html):
    builder = _Builder()
    builder.feed(pre_clean(html))
    body = Renderer().children(builder.root.kids, True)

    # one <h1> per page: demote every heading in the body (open + close tags)
    body = re.sub(r"<h([1-6])([ >])",
                  lambda m: "<h%d%s" % (min(int(m.group(1)) + 1, 6), m.group(2)), body)
    body = re.sub(r"</h([1-6])>",
                  lambda m: "</h%d>" % min(int(m.group(1)) + 1, 6), body)

    # tidy leftovers
    body = re.sub(r"<h([2-6])>(?:\s|<br>)*</h\1>", "", body)
    body = re.sub(r"</ul>\s*<ul>", "", body)
    body = re.sub(r"</ol>\s*<ol>", "", body)
    body = re.sub(r"<code>\s*</code>", "", body)
    body = re.sub(r"<p>\s*</p>", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.replace('href="/', 'href="%s/' % SITE_URL)
    body = body.replace('src="/', 'src="%s/' % SITE_URL)
    return body.strip()


# ==========================================================================
# Images
# ==========================================================================

def enhance_images(html, alt_base):
    counter = [0]

    def repl(m):
        tag = m.group(0)
        closing = "/>" if tag.rstrip().endswith("/>") else ">"
        inner = tag.rstrip()[: -len(closing)]
        counter[0] += 1
        existing = re.search(r'\balt\s*=\s*"([^"]*)"', inner, re.I)
        if not existing or not existing.group(1).strip():
            inner = re.sub(r'\s*\balt\s*=\s*"[^"]*"', "", inner, flags=re.I)
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


def localize_images(html, slug, image_cache):
    os.makedirs(IMAGES_DIR, exist_ok=True)

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

    urls = sorted(set(re.findall(
        r'src="(https?://[^"]+\.(?:png|jpe?g|gif|webp))"', html, flags=re.I)))
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
        html = html.replace('href="%s"' % url, 'href="%s"' % local)

    return html


# ==========================================================================
# Page assembly
# ==========================================================================

def text_preview(html, length=160):
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def fmt_date(iso):
    return datetime.fromisoformat(iso[:10]).strftime("%b %d, %Y")


POST_TEMPLATE = """
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
"""


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
        raw_content = e.get("content", {}).get("$t", "")

        print("  %s" % slug)
        body = normalize_body(raw_content)
        body = localize_images(body, slug, image_cache)
        body = enhance_images(body, title)

        desc = escape(text_preview(body), quote=True)
        read_mins = max(1, round(len(re.sub(r"<[^>]+>", " ", raw_content)) / 1000))
        labels_html = escape(" · ".join(labels[:4])) if labels else ""
        canonical = "%s/posts/%s.html" % (SITE_URL, slug)

        head = page_shell(title, desc, rel="../", current="blog",
                          canonical=canonical, ogtype="article")
        labels_block = (
            '<p class="post-labels mono"><b>%s</b></p>' % labels_html if labels_html else ""
        )
        page = head + (
            POST_TEMPLATE
            .replace("%%DATE%%", fmt_date(date_iso))
            .replace("%%READ%%", str(read_mins))
            .replace("%%H1%%", escape(title))
            .replace("%%LABELS%%", labels_block)
            .replace("%%ORIGIN%%", url)
            .replace("%%BODY%%", body)
        ) + FOOTER.replace("%%REL%%", "../")

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

    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i < len(posts) - 1 else None

        def block(p, direction):
            if not p:
                return "<span></span>"
            cls = " next" if direction == "Older" else ""
            return ('<a class="post-nav-item%s" href="%s.html">'
                    '<span class="dir">%s note</span><span class="t">%s</span></a>'
                    % (cls, p["slug"], direction, escape(p["title"])))

        nav_html = block(newer, "Newer") + block(older, "Older")
        fname = os.path.join(POSTS_DIR, "%s.html" % p["slug"])
        with open(fname) as f:
            page = f.read()
        with open(fname, "w") as f:
            f.write(page.replace("%%NAV%%", nav_html))

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
        "All %d notes and cheat sheets by Ibrahim Babashov — Linux, networking, "
        "AWS, Salt, Docker and more." % len(posts),
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

    write_sitemap(posts)

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
        "    <priority>%s</priority>\n  </url>" % u for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           '%s\n</urlset>\n' % body)
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write(xml)
    print("  sitemap.xml")


if __name__ == "__main__":
    main()
