// Runs in <head> before first paint: applies the saved theme, flags JS as
// available (so scroll-reveal content stays visible without JS), and syncs
// the browser theme-color. Kept tiny and synchronous on purpose.
(function () {
  var root = document.documentElement;
  var theme = "dark";

  try {
    theme = localStorage.getItem("theme") || "dark";
  } catch (e) {
    /* storage unavailable — keep default */
  }

  root.setAttribute("data-theme", theme);
  root.classList.add("js");

  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#07090f" : "#f6f6fa");

  // Safety net: if main.js never ran, don't leave reveal elements hidden.
  // (If it did run, window.__revealReady is set and we leave scroll reveals alone.)
  window.addEventListener("load", function () {
    setTimeout(function () {
      if (window.__revealReady) return;
      var els = document.querySelectorAll(".reveal:not(.in)");
      for (var i = 0; i < els.length; i++) els[i].classList.add("in");
    }, 1500);
  });
})();
