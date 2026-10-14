// ibrahimbabashov.com — small helpers: theme toggle + mobile nav

(function () {
  "use strict";

  // ---------- Theme (dark / light) ----------
  var root = document.documentElement;
  var toggle = document.querySelector(".theme-toggle");
  var storageKey = "theme";

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    if (toggle) toggle.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  // Respect saved preference, fall back to system preference.
  var saved = null;
  try {
    saved = localStorage.getItem(storageKey);
  } catch (e) {
    /* storage unavailable — ignore */
  }
  var prefersDark = window.matchMedia
    && window.matchMedia("(prefers-color-scheme: dark)").matches;

  applyTheme(saved || (prefersDark ? "dark" : "light"));

  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(storageKey, next);
      } catch (e) {
        /* ignore */
      }
    });
  }

  // ---------- Mobile navigation ----------
  var navToggle = document.querySelector(".nav-toggle");
  var navLinks = document.querySelector(".nav-links");

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var isOpen = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }
})();
