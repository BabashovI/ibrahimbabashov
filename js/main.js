// ibrahimbabashov.com — theme, nav, reading progress, reveal animations

(function () {
  "use strict";

  var root = document.documentElement;

  // ---------- Theme (dark default) ----------
  var toggle = document.querySelector(".theme-toggle");

  function currentTheme() {
    return root.getAttribute("data-theme") || "dark";
  }

  function refreshToggle() {
    if (toggle) toggle.textContent = currentTheme() === "dark" ? "☀️" : "🌙";
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

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var isOpen = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
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

  // ---------- Footer year ----------
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
