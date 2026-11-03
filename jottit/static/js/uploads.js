// Edit-page image uploads island. Drop or paste an image into the textarea,
// or pick one with the "Add an image" button: each file posts to
// site/uploads, and a "![Uploading …]()" placeholder at the caret is
// swapped for the Markdown image once the server answers. Failures drop
// the placeholder and show the server's message next to the buttons.
(() => {
  const form = document.getElementById("edit_form");
  const textarea = document.getElementById("content_text");
  const button = document.getElementById("image_button");
  const input = document.getElementById("image_input");
  const errorBox = document.getElementById("upload_error");
  if (!form || !textarea) return;

  const uploadUrl = form.dataset.uploadUrl;
  const maxBytes = parseInt(form.dataset.maxUploadBytes, 10) || 0;
  const TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  let counter = 0;

  const showError = (message) => {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = !message;
  };

  const changed = () => textarea.dispatchEvent(new Event("input"));

  const insertAtCaret = (text) => {
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? start;
    textarea.setRangeText(text, start, end, "end");
    changed();
  };

  const replaceText = (from, to) => {
    const at = textarea.value.indexOf(from);
    if (at === -1) return;
    const caret = textarea.selectionStart;
    textarea.setRangeText(to, at, at + from.length, "preserve");
    if (caret > at) {
      const pos = Math.max(at, caret + to.length - from.length);
      textarea.setSelectionRange(pos, pos);
    }
    changed();
  };

  const altText = (file) =>
    (file.name || "image").replace(/\.[^.]+$/, "").replace(/[\[\]\\]/g, "");

  const describeFailure = async (response) => {
    try {
      const body = await response.json();
      if (body.error) return body.error;
    } catch {
      /* not JSON — fall through */
    }
    if (response.status === 401) return "Sign in to this site to upload images.";
    if (response.status === 413) return "That image is too big.";
    return "Sorry, that image couldn't be uploaded.";
  };

  const upload = async (file) => {
    if (!TYPES.includes(file.type)) {
      showError("Only PNG, JPEG, GIF, and WebP images can be uploaded.");
      return;
    }
    if (maxBytes && file.size > maxBytes) {
      showError(`Images must be ${+(maxBytes / 1024 / 1024).toFixed(2)} MB or smaller.`);
      return;
    }
    showError("");
    const alt = altText(file);
    const placeholder = `![Uploading ${alt}…#${++counter}]()`;
    insertAtCaret(placeholder);

    const data = new FormData();
    data.append("file", file);
    let message;
    try {
      const response = await fetch(uploadUrl, { method: "POST", body: data });
      if (response.ok) {
        const { url } = await response.json();
        replaceText(placeholder, `![${alt}](${url})`);
        return;
      }
      message = await describeFailure(response);
    } catch {
      message = "Couldn't reach the server to upload that image.";
    }
    replaceText(placeholder, "");
    showError(message);
  };

  const uploadAll = (files) => {
    for (const file of files) upload(file);
  };

  const imageFiles = (list) => Array.from(list || []).filter((f) => f.type.startsWith("image/"));

  textarea.addEventListener("dragover", (e) => {
    if (!e.dataTransfer || !Array.from(e.dataTransfer.types).includes("Files")) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    textarea.classList.add("dropping");
  });

  textarea.addEventListener("dragleave", () => textarea.classList.remove("dropping"));

  textarea.addEventListener("drop", (e) => {
    textarea.classList.remove("dropping");
    const files = Array.from(e.dataTransfer?.files || []);
    if (!files.length) return;
    e.preventDefault();
    textarea.focus();
    uploadAll(files);
  });

  textarea.addEventListener("paste", (e) => {
    const files = imageFiles(e.clipboardData?.files);
    if (!files.length) return;
    e.preventDefault();
    uploadAll(files);
  });

  button?.addEventListener("click", () => input?.click());

  input?.addEventListener("change", () => {
    const files = Array.from(input.files || []);
    input.value = "";
    textarea.focus();
    uploadAll(files);
  });
})();
