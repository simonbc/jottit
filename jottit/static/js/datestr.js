// Relative-date ticker island. Re-renders any <time class="js-datestr"> on
// a cadence matched to the displayed unit (10s while showing seconds, 1m
// while showing minutes, 1h while showing hours, then static once ≥4 days).
// Self-discovering: no-op when nothing on the page has .js-datestr.
(() => {
  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];

  const datestr = (then, now) => {
    const deltaSec = Math.floor((now - then) / 1000);
    const sign = deltaSec < 0 ? -1 : 1;
    const absSec = Math.abs(deltaSec);
    const absDays = Math.floor(absSec / 86400);

    const ago = (n, unit) => {
      const m = Math.abs(n);
      return `${m} ${unit}${m === 1 ? "" : "s"} ago`;
    };

    if (absDays) {
      if (absDays < 4) return ago(absDays * sign, "day");
      let out = `${MONTHS[then.getUTCMonth()]} ${then.getUTCDate()}`;
      if (then.getUTCFullYear() !== now.getUTCFullYear() || sign < 0) {
        out += `, ${then.getUTCFullYear()}`;
      }
      return out;
    }
    if (absSec > 3600) return ago(Math.floor(absSec / 3600) * sign, "hour");
    if (absSec > 60) return ago(Math.floor(absSec / 60) * sign, "minute");
    if (absSec) return ago(deltaSec, "second");
    return "0 seconds ago";
  };

  const nextDelayMs = (then, now) => {
    const absSec = Math.abs(Math.floor((now - then) / 1000));
    if (absSec < 60) return (10 - (absSec % 10)) * 1000;
    if (absSec < 3600) return 60_000;
    if (absSec < 86400) return 3_600_000;
    return null;
  };

  const tick = (el) => {
    const then = new Date(el.getAttribute("datetime"));
    if (isNaN(then.getTime())) return;
    const now = new Date();
    el.textContent = datestr(then, now);
    const delay = nextDelayMs(then, now);
    if (delay !== null) setTimeout(() => tick(el), delay);
  };

  for (const el of document.querySelectorAll(".js-datestr")) tick(el);
})();
