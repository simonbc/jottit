// Revision banner dropdown. Replaces "#N (YYYY-MM-DD)" option labels with
// relative-time ("9 seconds ago") strings on first paint, and navigates
// to ?r=N when the user picks a revision.
(() => {
  const select = document.getElementById("change_rev");
  if (!select) return;

  select.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("r", select.value);
    window.location.href = url.href;
  });

  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const datestr = (then, now) => {
    const sec = Math.max(0, Math.floor((now - then) / 1000));
    const ago = (n, unit) => `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    const days = Math.floor(sec / 86400);
    if (days >= 4) return `${MONTHS[then.getUTCMonth()]} ${then.getUTCDate()}`;
    if (days) return ago(days, "day");
    if (sec >= 3600) return ago(Math.floor(sec / 3600), "hour");
    if (sec >= 60) return ago(Math.floor(sec / 60), "minute");
    if (sec) return ago(sec, "second");
    return "0 seconds ago";
  };

  const now = new Date();
  for (const opt of select.options) {
    const rev = opt.dataset.rev;
    const iso = opt.dataset.datetime;
    if (!rev || !iso) continue;
    const then = new Date(iso);
    if (isNaN(then.getTime())) continue;
    opt.text = `#${rev} (${datestr(then, now)})`;
  }
})();
