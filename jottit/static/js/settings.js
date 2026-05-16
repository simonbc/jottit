// Settings page island: live-preview title/subtitle into the site chrome
// header on input, and POST the full form on a 700ms idle debounce. The
// explicit Save button still works with JS off; #settings_status surfaces
// the autosave state.
(() => {
  const form = document.getElementById("settings_form");
  if (!form) return;

  const titleInput = document.getElementById("title");
  const subtitleInput = document.getElementById("subtitle_input");
  const status = document.getElementById("settings_status");
  const headerTitle = document.querySelector(".site-title a");
  const headerSubtitle = document.getElementById("subtitle");

  const setStatus = (text) => { if (status) status.textContent = text; };

  if (titleInput && headerTitle) {
    titleInput.addEventListener("input", () => {
      headerTitle.textContent = titleInput.value;
    });
  }
  if (subtitleInput && headerSubtitle) {
    subtitleInput.addEventListener("input", () => {
      headerSubtitle.textContent = subtitleInput.value;
    });
  }

  const DEBOUNCE_MS = 700;
  let timer = null;

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
})();
