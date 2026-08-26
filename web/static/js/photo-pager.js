// Left/right arrows walk the trip slide by slide. The URLs come from the
// page itself rather than being computed here, so the order stays defined
// in one place - build.py.
(function () {
  const pager = document.querySelector("[data-photo-pager]");
  if (!pager) return;
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || e.target.isContentEditable) return;
    const url = e.key === "ArrowLeft" ? pager.dataset.prev
              : e.key === "ArrowRight" ? pager.dataset.next
              : null;
    if (url) { e.preventDefault(); location.href = url; }
  });
})();
