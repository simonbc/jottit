// Edit-page "Formatting help" toggle. Swaps the right-hand pane between
// the live preview and a static markdown reference table; the link text
// flips from "Formatting help" to "Return to preview".
(() => {
  const link = document.getElementById("formatting_help_link");
  const preview = document.getElementById("preview");
  const help = document.getElementById("help");
  if (!link || !preview || !help) return;

  const setHelp = (showHelp) => {
    preview.hidden = showHelp;
    help.hidden = !showHelp;
    link.textContent = showHelp ? "Return to preview" : "Formatting help";
  };

  link.addEventListener("click", (e) => {
    e.preventDefault();
    setHelp(help.hidden);
  });
})();
