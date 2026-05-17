// Sidebar "Create a new page" island. The button collapses to expose the
// name-input form; the close link collapses it back. Without JS the form is
// already expanded (the [hidden] attr is the JS-on state), so the static
// flow still works.
(() => {
  const form = document.getElementById("new_page_form");
  const toggle = document.querySelector(".button-toggle-newpage");
  const button = document.getElementById("new_page");
  const input = document.getElementById("new_page_input");
  const close = document.querySelector(".link-close-newpage");
  const name = document.getElementById("new_page_name");
  if (!toggle || !button || !input || !form) return;

  toggle.addEventListener("click", () => {
    button.hidden = true;
    input.hidden = false;
    name?.focus();
  });

  close?.addEventListener("click", (e) => {
    e.preventDefault();
    input.hidden = true;
    button.hidden = false;
  });

  // Build /<slug>/<page>?m=edit instead of letting the GET submit land on
  // the site root with ?name=<page> (which the home-page handler ignores).
  form.addEventListener("submit", (e) => {
    const value = name?.value.trim();
    if (!value) return;
    e.preventDefault();
    const base = form.getAttribute("action") || "/";
    const href = `${base}${encodeURIComponent(value)}?m=edit`;
    window.location.assign(href);
  });
})();
