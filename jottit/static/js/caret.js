// Edit-page caret + scroll persistence island. On enter (desktop only),
// focus the textarea and place the cursor at the saved position; on blur
// and on submit, capture the current position into hidden fields so the
// server can store it for next time.
//
// Mobile is skipped on purpose — auto-focus there pops the soft keyboard
// and reflows the layout mid-render.
(() => {
  const textarea = document.getElementById("content_text");
  const caretField = document.getElementById("caret_pos");
  const scrollField = document.getElementById("scroll_pos");
  if (!textarea || !caretField || !scrollField) return;

  const DESKTOP_MIN = 768;
  const isDesktop = () => window.innerWidth >= DESKTOP_MIN;

  if (isDesktop()) {
    try {
      textarea.focus();
      let caret = parseInt(caretField.value, 10) || 0;
      const scroll = parseInt(scrollField.value, 10) || 0;
      // caret_pos == 0 on a non-empty textarea usually means "never edited"
      // (DB default). Default the cursor to end-of-content so the user can
      // resume typing; explicit non-zero positions are honored exactly.
      if (caret === 0 && textarea.value.length > 0) {
        caret = textarea.value.length;
      }
      const pos = Math.min(caret, textarea.value.length);
      textarea.setSelectionRange(pos, pos);
      textarea.scrollTop = scroll;
    } catch {
      /* older browsers / detached element */
    }
  }

  const capture = () => {
    if (!isDesktop()) return;
    caretField.value = textarea.selectionStart || 0;
    scrollField.value = textarea.scrollTop || 0;
  };

  textarea.addEventListener("blur", capture);
  textarea.form?.addEventListener("submit", capture);
})();
