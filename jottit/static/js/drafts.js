// Edit-page drafts island. Stores the textarea content in localStorage on
// every change (debounced 1s); if a stored draft differs from the server
// content when the page loads, shows a restore banner. On successful submit
// the draft is cleared.
//
// Storage shape: { content: string, savedAt: ms-epoch } under
// `jottit-draft:${pathname}`. Drafts older than 30 days are pruned on load.
(() => {
  const form = document.getElementById("edit_form");
  const textarea = document.getElementById("content_text");
  const banner = document.getElementById("draft_banner");
  const restore = document.getElementById("draft_restore");
  const discard = document.getElementById("draft_discard");
  const status = document.getElementById("draft_status");
  if (!form || !textarea) return;

  const KEY = `jottit-draft:${location.pathname}`;
  const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
  const DEBOUNCE_MS = 1000;
  const original = form.dataset.originalContent ?? "";

  const read = () => {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Date.now() - parsed.savedAt > MAX_AGE_MS) {
        localStorage.removeItem(KEY);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  };

  const write = (content) => {
    try {
      localStorage.setItem(KEY, JSON.stringify({ content, savedAt: Date.now() }));
    } catch {
      // Quota / private mode — silently fall back to in-memory only.
    }
  };

  const clear = () => {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  };

  const stored = read();
  if (stored && stored.content !== original && stored.content !== textarea.value && banner) {
    banner.hidden = false;
  }

  restore?.addEventListener("click", () => {
    if (stored) textarea.value = stored.content;
    banner.hidden = true;
    textarea.focus();
  });

  discard?.addEventListener("click", () => {
    clear();
    banner.hidden = true;
    textarea.focus();
  });

  let timer = null;
  textarea.addEventListener("input", () => {
    if (status) status.textContent = "unsaved";
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      write(textarea.value);
      if (status) status.textContent = "draft saved";
    }, DEBOUNCE_MS);
  });

  form.addEventListener("submit", () => {
    clear();
  });
})();
