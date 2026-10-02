const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const rootPath = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(rootPath, "src/site.js"), "utf8");
const boot = execFileSync("python", ["-c", "from scripts.build_site import LANG_BOOT; print(LANG_BOOT)"],
  { cwd: rootPath, encoding: "utf8" }).replace(/<\/?script>/g, "");

function element(attrs = {}) {
  return {
    attrs: { ...attrs }, events: {}, textContent: "", hidden: false,
    getAttribute(k) { return this.attrs[k] ?? null; },
    setAttribute(k, v) { this.attrs[k] = v; },
    removeAttribute(k) { delete this.attrs[k]; },
    hasAttribute(k) { return k in this.attrs; },
    addEventListener(k, fn) { this.events[k] = fn; }
  };
}

function load({ url = "https://example.test/topsscs/index.html", saved = {}, blocked = false } = {}) {
  const storage = { ...saved };
  const location = new URL(url);
  const root = element({ "data-title-en": "Japan ranking" });
  root.lang = "ja";
  const toggle = element();
  const option = element({ "data-ja": "確定版", "data-en": "Final" });
  option.value = "2021-2025/index.html";
  const links = ["world/index.html", "methodology.html#championship", "https://doi.org/10.1/test", "#main"].map(href => element({ href }));
  const buttons = ["full", "first", "frac"].map(mode => element({ "data-mode": mode }));
  const panels = ["full", "first", "frac"].map(mode => element({ "data-mode": mode }));
  const selectors = {
    "[data-lang-toggle]": [toggle], "option[data-en]": [option], "a[href]": links,
    "select[data-nav] option": [option], "select[data-nav]": [],
    ".mode-switch button": buttons, ".mode-panel": panels
  };
  let ready;
  const document = {
    documentElement: root, title: "日本ランキング",
    querySelectorAll(selector) { return selectors[selector] || []; },
    addEventListener(event, fn) { if (event === "DOMContentLoaded") ready = fn; }
  };
  const context = vm.createContext({
    URL, URLSearchParams, document, location, window: {},
    history: { replaceState(_state, _title, href) { location.href = href; } },
    localStorage: {
      getItem(key) { if (blocked) throw new Error("blocked"); return storage[key] || null; },
      setItem(key, value) { if (blocked) throw new Error("blocked"); storage[key] = value; }
    }
  });
  vm.runInContext(boot, context);
  vm.runInContext(source, context);
  ready();
  return { root, document, toggle, option, links, buttons, panels, storage, location };
}

test("Japan/Japanese is the initial view; language and counting preferences survive navigation", () => {
  const page = load();
  assert.equal(page.root.lang, "ja");
  assert.equal(page.option.textContent, "確定版");
  page.buttons[2].events.click();
  assert.deepEqual(page.panels.map(p => p.hidden), [true, true, false]);
  page.toggle.events.click();
  assert.equal(page.document.title, "Japan ranking");
  assert.equal(page.root.lang, "en");
  assert.equal(page.option.textContent, "Final");
  assert.equal(new URL(page.option.value).search, "?lang=en");
  assert.equal(new URL(page.links[0].attrs.href).search, "?lang=en");
  assert.equal(new URL(page.links[1].attrs.href).hash, "#championship-en");
  assert.equal(page.links[2].attrs.href, "https://doi.org/10.1/test");
  assert.equal(page.links[3].attrs.href, "#main");
  const next = load({ url: page.links[0].attrs.href, saved: page.storage });
  assert.equal(next.root.lang, "en");
  assert.deepEqual(next.panels.map(p => p.hidden), [true, true, false]);
});

test("explicit language overrides storage and toggling updates the URL for reload", () => {
  const page = load({ url: "https://example.test/?lang=en", saved: { "topsscs-lang": "ja" } });
  assert.equal(page.root.lang, "en");
  page.toggle.events.click();
  assert.equal(page.root.lang, "ja");
  assert.equal(page.document.title, "日本ランキング");
  assert.equal(page.location.searchParams.get("lang"), "ja");
  assert.equal(new URL(page.links[1].attrs.href).hash, "#championship");
  assert.equal(load({ url: page.location.href, saved: page.storage }).root.lang, "ja");
});

test("English query and local-file navigation work with storage blocked", () => {
  const page = load({ url: "file:///site/index.html?lang=en", blocked: true });
  assert.equal(page.root.lang, "en");
  assert.equal(load({ url: page.links[0].attrs.href, blocked: true }).root.lang, "en");
  page.toggle.events.click();
  assert.equal(page.root.lang, "ja");
});

test("invalid stored preferences fall back to Japanese and full count", () => {
  const page = load({ saved: { "topsscs-lang": "invalid", "topsscs-mode": "invalid" } });
  assert.equal(page.root.lang, "ja");
  assert.deepEqual(page.panels.map(p => p.hidden), [false, true, true]);
});
