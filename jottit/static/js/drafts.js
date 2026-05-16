// Edit-page drafts island. Auto-restores any in-progress draft on load (no
// click needed), and offers a revert-to-live link to undo. On every change
// the textarea content is written back to localStorage (debounced 1s); on
// successful submit the draft is cleared.
//
// Storage shape: { content: string, savedAt: ms-epoch } under
// `jottit-draft:${pathname}`. Drafts older than 30 days are pruned on load.
(() => {
  const form = document.getElementById("edit_form");
  const textarea = document.getElementById("content_text");
  const banner = document.getElementById("draft_banner");
  const revert = document.getElementById("draft_revert");
  const dismiss = document.getElementById("draft_dismiss");
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

  // Auto-restore: if there's a stored draft that differs from the server
  // content, swap it in immediately and surface the revert banner.
  const stored = read();
  if (stored && stored.content !== original && banner) {
    textarea.value = stored.content;
    banner.hidden = false;
  }

  revert?.addEventListener("click", () => {
    textarea.value = original;
    clear();
    banner.hidden = true;
    textarea.focus();
    textarea.dispatchEvent(new Event("input"));
  });

  dismiss?.addEventListener("click", () => {
    banner.hidden = true;
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
