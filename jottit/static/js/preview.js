// Live markdown preview island. Re-renders the preview pane on every
// keystroke (debounced 150ms) using marked.js, which loads alongside this
// file from /static/js/vendor/marked.min.js. The server is the source of
// truth on Save — minor render drift here is accepted.
(() => {
  const textarea = document.getElementById("content_text");
  const preview = document.getElementById("preview");
  if (!textarea || !preview) return;

  // Uploaded images are written as `/site/uploads/<name>`; on a secret-URL
  // site they live under the site's prefix, as the server renders them.
  const siteRoot = textarea.form?.dataset.siteRoot || "/";

  const render = () => {
    if (!window.marked) return;
    try {
      preview.innerHTML = window.marked.parse(textarea.value || "");
      for (const img of preview.querySelectorAll('img[src^="/site/uploads/"]')) {
        img.setAttribute("src", siteRoot + img.getAttribute("src").slice(1));
      }
    } catch {
      // Leave the preview stale; server-side render still wins on Save.
    }
  };

  let timer = null;
  textarea.addEventListener("input", () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(render, 150);
  });

  // Re-render once marked has loaded (it's also deferred); fall through
  // immediately if it's already there from cache.
  if (window.marked) render();
  else window.addEventListener("load", render, { once: true });
})();
