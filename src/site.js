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

  var LANG_KEY = "topsscs-lang";

  function localizedURL(href, lang) {
    var url = new URL(href, location.href);
    if (url.origin !== location.origin || url.protocol !== location.protocol) return href;
    url.searchParams.set("lang", lang);
    // The methodology has a separate article (and anchor IDs) per language.
    if (/^#(scopes|modes|championship)(-en)?$/.test(url.hash)) {
      url.hash = url.hash.replace(/-en$/, "") + (lang === "en" ? "-en" : "");
    }
    return url.href;
  }

  function applyLang(lang) {
    var root = document.documentElement;
    if (lang === "en") { root.setAttribute("data-lang", "en"); root.lang = "en"; }
    else { root.removeAttribute("data-lang"); root.lang = "ja"; }
    // texts that cannot hold markup: <option> labels and the document title
    document.querySelectorAll("option[data-en]").forEach(function (o) {
      o.textContent = o.getAttribute(lang === "en" ? "data-en" : "data-ja");
    });
    if (!root.hasAttribute("data-title-ja")) root.setAttribute("data-title-ja", document.title);
    document.title = root.getAttribute(lang === "en" ? "data-title-en" : "data-title-ja") || document.title;
    document.querySelectorAll("[data-lang-toggle]").forEach(function (b) {
      b.setAttribute("aria-label", lang === "en" ? "日本語に切り替え" : "Switch to English");
    });
    // Carry the preference in local links too: storage may be blocked (or file://).
    document.querySelectorAll("a[href]").forEach(function (a) {
      var href = a.getAttribute("href");
      if (href.charAt(0) !== "#") a.setAttribute("href", localizedURL(href, lang));
    });
    document.querySelectorAll("select[data-nav] option").forEach(function (o) {
      o.value = localizedURL(o.value, lang);
    });
    // Toggling a shared ?lang=en page must also survive a reload.
    try { history.replaceState(null, "", localizedURL(location.href, lang)); } catch (e) { /* file:// */ }
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(stored());
    applyLang(document.documentElement.getAttribute("data-lang") === "en" ? "en" : "ja");
    document.querySelectorAll("[data-lang-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var next = document.documentElement.getAttribute("data-lang") === "en" ? "ja" : "en";
        try { localStorage.setItem(LANG_KEY, next); } catch (e) { /* storage unavailable */ }
        applyLang(next);
        if (window.gtag) window.gtag("event", "language", { lang: next });
      });
    });
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
