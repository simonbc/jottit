// Design panel island. Two range sliders (hue, brightness) drive a
// continuous color picker — header is hsl(hue, 100%, lightness%) where
// lightness comes from brightness, and title + subtitle are derived from
// header for contrast. Same look as the 21 ship-with-new-site palettes
// in jottit/db.py:COLOR_SCHEMES, just continuous.
//
// Font + size dropdowns each map to a CSS custom property on :root so
// the chrome updates instantly. Every change debounces a POST so the
// server stores the new values — no Save button.
(() => {
  const form = document.getElementById("design");
  if (!form) return;

  // Convert HSL (h: 0..360, s: 0..100, l: 0..100) to a #rrggbb hex string,
  // because the server's _HEX_COLOR_RE only accepts hex.
  const hslToHex = (h, s, l) => {
    l /= 100;
    const a = (s * Math.min(l, 1 - l)) / 100;
    const f = (n) => {
      const k = (n + h / 30) % 12;
      const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
      return Math.round(255 * c).toString(16).padStart(2, "0");
    };
    return `#${f(0)}${f(8)}${f(4)}`;
  };

  // Brightness 0..300 maps to lightness 99..16 (linear fit through the
  // four lightness anchors used by COLOR_SCHEMES: b=20 ≈ L92, b=140 ≈ L45,
  // b=196 ≈ L23, b=214 ≈ L16). Title is white on dark headers, black on
  // light. Subtitle is the complementary lightness in the same hue.
  const compute = (hue, brightness) => {
    const headerL = Math.max(5, Math.min(95, 99 - brightness * 0.39));
    const subtitleL = headerL < 50 ? 85 : 20;
    return {
      header: hslToHex(hue, 100, headerL),
      title: headerL < 50 ? "#ffffff" : "#000000",
      subtitle: hslToHex(hue, 100, subtitleL),
    };
  };

  const hueInput = document.getElementById("hue");
  const brightnessInput = document.getElementById("brightness");
  const headerColor = document.getElementById("header_color");
  const titleColor = document.getElementById("title_color");
  const subtitleColor = document.getElementById("subtitle_color");
  const swatch = document.getElementById("color_swatch");
  const status = document.getElementById("design_status");
  const root = document.documentElement.style;

  const refreshFromSliders = () => {
    const hue = parseInt(hueInput.value, 10) || 0;
    const brightness = parseInt(brightnessInput.value, 10) || 0;
    const c = compute(hue, brightness);
    headerColor.value = c.header;
    titleColor.value = c.title;
    subtitleColor.value = c.subtitle;
    root.setProperty("--color-header", c.header);
    root.setProperty("--color-title", c.title);
    root.setProperty("--color-subtitle", c.subtitle);
    if (swatch) swatch.style.background = c.header;
    // Re-tint the brightness slider's track to the current hue.
    if (brightnessInput) brightnessInput.style.setProperty("--track-hue", hue);
  };

  hueInput?.addEventListener("input", refreshFromSliders);
  brightnessInput?.addEventListener("input", refreshFromSliders);
  refreshFromSliders();

  // Font + size dropdowns: bind each to its CSS custom property.
  const fontStack = (label) => label ? `${label.replace(/_/g, " ")}, sans-serif` : "";
  const bindFont = (id, prop) => {
    const el = document.getElementById(id);
    el?.addEventListener("change", () => root.setProperty(prop, fontStack(el.value)));
  };
  const bindSize = (id, prop) => {
    const el = document.getElementById(id);
    el?.addEventListener("change", () => root.setProperty(prop, `${el.value}%`));
  };
  bindFont("title_font", "--font-family-title");
  bindFont("subtitle_font", "--font-family-subtitle");
  bindFont("headings_font", "--font-family-headings");
  bindFont("content_font", "--font-family-content");
  // Sizes drive the chrome's typography via percent values; the CSS picks
  // these up wherever it references --font-size-*-mult.
  bindSize("title_size", "--font-size-title");
  bindSize("subtitle_size", "--font-size-subtitle");
  bindSize("headings_size", "--font-size-headings");
  bindSize("content_size", "--font-size-content");

  // Debounced autosave — same shape as settings.js.
  const DEBOUNCE_MS = 600;
  let timer = null;
  const setStatus = (text) => { if (status) status.textContent = text; };

  const save = () => {
    timer = null;
    setStatus("saving…");
    fetch(form.action || window.location.pathname, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      redirect: "manual",
    }).then(() => {
      setStatus("saved");
      setTimeout(() => { if (timer === null) setStatus(""); }, 1500);
    }).catch(() => {
      setStatus("save failed — try again");
    });
  };

  const schedule = () => {
    setStatus("");
    if (timer) clearTimeout(timer);
    timer = setTimeout(save, DEBOUNCE_MS);
  };

  form.addEventListener("input", schedule);
  form.addEventListener("change", schedule);

  // Revert: snapshot every field's value at page load and restore them on
  // click. With autosave on, the link doesn't reload the page — the cancel
  // semantics live entirely in JS.
  const snapshot = new Map();
  for (const el of form.querySelectorAll("input, select")) {
    snapshot.set(el, el.value);
  }
  const revertLink = form.querySelector("a.button-cancel");
  revertLink?.addEventListener("click", (e) => {
    e.preventDefault();
    for (const [el, value] of snapshot) el.value = value;
    refreshFromSliders();
    // Re-fire change events so font / size dropdowns push values back
    // through their CSS custom property bindings.
    for (const el of form.querySelectorAll("select")) {
      el.dispatchEvent(new Event("change"));
    }
    schedule();
  });
})();
