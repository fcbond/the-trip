// Two ways to read a day: slides after the text, or slides alongside it.
// The choice is remembered, because you page through days one after
// another and re-picking on every page would be tedious.
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
  apply(saved === "alongside" ? "alongside" : "below");

  toggle.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-layout-value]");
    if (btn) apply(btn.dataset.layoutValue);
  });
})();
