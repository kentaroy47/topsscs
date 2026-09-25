// Counting-mode switch (remembered per browser) and edition selector.
(function () {
  var KEY = "topsscs-mode";
  var MODES = ["full", "first", "frac"];

  function stored() {
    try {
      var m = localStorage.getItem(KEY);
      return MODES.indexOf(m) >= 0 ? m : "full";
    } catch (e) {
      return "full";
    }
  }

  function apply(mode) {
    document.querySelectorAll(".mode-panel").forEach(function (el) {
      el.hidden = el.getAttribute("data-mode") !== mode;
    });
    document.querySelectorAll(".mode-switch button").forEach(function (b) {
      b.setAttribute("aria-checked", b.getAttribute("data-mode") === mode ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(stored());
    document.querySelectorAll(".mode-switch button").forEach(function (b) {
      b.addEventListener("click", function () {
        var m = b.getAttribute("data-mode");
        try { localStorage.setItem(KEY, m); } catch (e) { /* storage unavailable */ }
        apply(m);
        if (window.gtag) window.gtag("event", "counting_mode", { mode: m });
      });
    });
    document.querySelectorAll("select[data-nav]").forEach(function (s) {
      s.addEventListener("change", function () {
        if (window.gtag) window.gtag("event", "edition_change", { edition: s.options[s.selectedIndex].text });
        location.href = s.value;
      });
    });
  });
})();
