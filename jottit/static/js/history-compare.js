// History-page compare island. Enables the Compare button only when
// exactly two revision checkboxes are picked; once two are picked, the
// rest are disabled so users don't have to uncheck to swap.
(() => {
  const form = document.getElementById("history_form");
  const button = document.getElementById("history_compare");
  if (!form || !button) return;

  const boxes = Array.from(form.querySelectorAll('input[type="checkbox"][name="r"]'));
  if (boxes.length < 2) return;

  const sync = () => {
    const checked = boxes.filter((b) => b.checked);
    button.disabled = checked.length !== 2;
    const cap = checked.length >= 2;
    for (const b of boxes) b.disabled = cap && !b.checked;
  };

  for (const b of boxes) b.addEventListener("change", sync);
  sync();
})();
