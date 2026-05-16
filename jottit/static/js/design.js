// Design page live preview. Mirrors form input changes into CSS custom
// properties on :root so the chrome re-themes without a round-trip; the
// server is the source of truth on submit and re-renders on next load.
//
// The font label → stack mapping mirrors design_style.html on the server:
// labels look like "Helvetica Neue" but the value we feed into the design
// row is the same string (with _ replaced by space when rendered), then
// suffixed with sans-serif on the server.
(() => {
  const form = document.getElementById("design");
  if (!form) return;

  const root = document.documentElement.style;

  const bind = (id, prop, transform = (v) => v) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => root.setProperty(prop, transform(el.value)));
  };

  const fontStack = (label) =>
    label ? `${label.replace(/_/g, " ")}, sans-serif` : "";

  bind("header_color", "--color-header");
  bind("title_color", "--color-title");
  bind("subtitle_color", "--color-subtitle");

  bind("title_font", "--font-family-title", fontStack);
  bind("subtitle_font", "--font-family-subtitle", fontStack);
  bind("headings_font", "--font-family-headings", fontStack);
  bind("content_font", "--font-family-content", fontStack);

  // Range outputs: show the numeric value next to the slider.
  for (const range of form.querySelectorAll("input[type=range]")) {
    const out = document.getElementById(`${range.id}_out`);
    if (!out) continue;
    const sync = () => { out.textContent = range.value; };
    sync();
    range.addEventListener("input", sync);
  }
})();
