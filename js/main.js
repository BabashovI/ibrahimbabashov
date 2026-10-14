// ibrahimbabashov.com — theme, nav, reading progress, reveal animations

(function () {
  "use strict";

  var root = document.documentElement;

  // ---------- Theme (dark default) ----------
  var toggle = document.querySelector(".theme-toggle");

  function currentTheme() {
    return root.getAttribute("data-theme") || "dark";
  }

  function syncThemeColor(theme) {
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#07090f" : "#f6f6fa");
  }

  function refreshToggle() {
    var dark = currentTheme() === "dark";
    if (toggle) {
      toggle.textContent = dark ? "☀️" : "🌙";
      toggle.setAttribute(
        "aria-label",
        dark ? "Switch to light theme" : "Switch to dark theme"
      );
      toggle.setAttribute("aria-pressed", dark ? "true" : "false");
    }
    syncThemeColor(dark ? "dark" : "light");
  }

  refreshToggle();

  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      refreshToggle();
      try {
        localStorage.setItem("theme", next);
      } catch (e) {
        /* storage unavailable — ignore */
      }
    });
  }

  // ---------- Mobile navigation ----------
  var navToggle = document.querySelector(".nav-toggle");
  var navLinks = document.querySelector(".nav-links");

  function closeNav() {
    if (!navLinks) return;
    navLinks.classList.remove("open");
    if (navToggle) navToggle.setAttribute("aria-expanded", "false");
  }

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var isOpen = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    // Close after choosing a link
    navLinks.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeNav();
    });

    // Close when clicking outside the header
    document.addEventListener("click", function (e) {
      if (navLinks.classList.contains("open") && !e.target.closest(".nav")) {
        closeNav();
      }
    });

    // Close on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeNav();
    });
  }

  // ---------- Reading progress (post pages) ----------
  var bar = document.getElementById("progress-bar");

  if (bar) {
    var updateProgress = function () {
      var doc = document.documentElement;
      var max = doc.scrollHeight - window.innerHeight;
      var pct = max > 0 ? (window.scrollY / max) * 100 : 0;
      bar.style.width = pct + "%";
    };
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  // ---------- Reveal on scroll ----------
  var revealEls = Array.prototype.slice.call(document.querySelectorAll(".reveal"));

  if (revealEls.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    revealEls.forEach(function (el) {
      io.observe(el);
    });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add("in");
    });
  }

  // Tells js/theme-init.js that reveal handling is active, so its watchdog
  // does not force-reveal everything on load.
  window.__revealReady = true;

  // ---------- Footer year ----------
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
