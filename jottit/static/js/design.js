// Design panel island. Two range sliders (hue, brightness) snap to one
// of the 21 hard-coded palettes that ship with new sites; each scheme
// supplies a matched header / title / subtitle color, so a single slider
// gesture re-themes the site chrome end-to-end.
//
// Font + size dropdowns each map to a CSS custom property on :root so
// the chrome updates instantly. Every change debounces a POST so the
// server stores the new values — no Save button.
//
// Mirrors jottit/db.py:COLOR_SCHEMES.
(() => {
  const form = document.getElementById("design");
  if (!form) return;

  const SCHEMES = [
    { header: "#520000", title: "#fff", subtitle: "#ffbfbf", hue: 0,   brightness: 214 },
    { header: "#523000", title: "#fff", subtitle: "#ffe5bf", hue: 25,  brightness: 214 },
    { header: "#515200", title: "#fff", subtitle: "#feffbf", hue: 43,  brightness: 214 },
    { header: "#2c5200", title: "#fff", subtitle: "#e2ffbf", hue: 62,  brightness: 214 },
    { header: "#003452", title: "#fff", subtitle: "#bfe8ff", hue: 143, brightness: 214 },
    { header: "#001152", title: "#fff", subtitle: "#bfcdff", hue: 161, brightness: 214 },
    { header: "#4d0052", title: "#fff", subtitle: "#fbbfff", hue: 210, brightness: 214 },
    { header: "#520036", title: "#fff", subtitle: "#ffbfe9", hue: 227, brightness: 214 },
    { header: "#760000", title: "#fff", subtitle: "#ffbfbf", hue: 0,   brightness: 196 },
    { header: "#764000", title: "#fff", subtitle: "#ffe2bf", hue: 23,  brightness: 196 },
    { header: "#087600", title: "#fff", subtitle: "#c4ffbf", hue: 82,  brightness: 196 },
    { header: "#004876", title: "#fff", subtitle: "#bfe6ff", hue: 144, brightness: 196 },
    { header: "#760043", title: "#fff", subtitle: "#ffbfe3", hue: 231, brightness: 196 },
    { header: "#92e600", title: "#000", subtitle: "#3a5c00", hue: 58,  brightness: 140 },
    { header: "#d7ecff", title: "#000", subtitle: "#003566", hue: 148, brightness: 20  },
    { header: "#d8ffd7", title: "#000", subtitle: "#026600", hue: 84,  brightness: 20  },
    { header: "#fcd7ff", title: "#000", subtitle: "#5e0066", hue: 209, brightness: 20  },
    { header: "#ffffd7", title: "#000", subtitle: "#656600", hue: 43,  brightness: 20  },
    { header: "#ffd7d7", title: "#000", subtitle: "#660000", hue: 0,   brightness: 20  },
    { header: "#d7fff9", title: "#000", subtitle: "#006656", hue: 121, brightness: 20  },
    { header: "#d7d7ff", title: "#000", subtitle: "#000066", hue: 170, brightness: 20  },
  ];

  // Hue distance is circular (0° == 360°); brightness is linear over 0..300.
  // Normalise both before Euclidean distance so neither axis dominates.
  const nearestScheme = (hue, brightness) => {
    let best = SCHEMES[0];
    let bestDist = Infinity;
    for (const s of SCHEMES) {
      const dh = Math.min(Math.abs(s.hue - hue), 360 - Math.abs(s.hue - hue)) / 180;
      const db = (s.brightness - brightness) / 300;
      const d = dh * dh + db * db;
      if (d < bestDist) { bestDist = d; best = s; }
    }
    return best;
  };

  const hueInput = document.getElementById("hue");
  const brightnessInput = document.getElementById("brightness");
  const headerColor = document.getElementById("header_color");
  const titleColor = document.getElementById("title_color");
  const subtitleColor = document.getElementById("subtitle_color");
  const swatch = document.getElementById("color_swatch");
  const status = document.getElementById("design_status");
  const root = document.documentElement.style;

  const applyScheme = (scheme) => {
    headerColor.value = scheme.header;
    titleColor.value = scheme.title;
    subtitleColor.value = scheme.subtitle;
    root.setProperty("--color-header", scheme.header);
    root.setProperty("--color-title", scheme.title);
    root.setProperty("--color-subtitle", scheme.subtitle);
    if (swatch) swatch.style.background = scheme.header;
    // Re-tint the brightness slider's track to the current hue.
    if (brightnessInput) brightnessInput.style.setProperty("--track-hue", scheme.hue);
  };

  const refreshFromSliders = () => {
    const hue = parseInt(hueInput.value, 10) || 0;
    const brightness = parseInt(brightnessInput.value, 10) || 0;
    applyScheme(nearestScheme(hue, brightness));
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
