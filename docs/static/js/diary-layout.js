// Two ways to read a day: slides alongside the text (the default, and what
// the CSS does on its own) or after it. The choice is remembered, because
// you page through days one after another and re-picking on every page
// would be tedious. Only "below" is stored as a departure from the
// default, so the page renders correctly before this script runs.
(function () {
  const page = document.querySelector("[data-diary-layout]");
  const toggle = document.querySelector("[data-layout-toggle]");
  if (!page || !toggle) return;

  const KEY = "trip-diary-layout";
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* private window */ }

  function apply(value) {
    page.dataset.layout = value;
    toggle.querySelectorAll("button").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.layoutValue === value)));
    try { localStorage.setItem(KEY, value); } catch (e) { /* ignore */ }
  }

  // Only shown once JS is running: without it the toggle would do nothing.
  toggle.hidden = false;
  apply(saved === "below" ? "below" : "alongside");

  toggle.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-layout-value]");
    if (btn) apply(btn.dataset.layoutValue);
  });
})();
