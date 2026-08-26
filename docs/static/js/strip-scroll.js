// Toggles edge-fade visibility on horizontally scrollable strips, so the
// "more to scroll" hint disappears once there's nothing left in that direction.
(function () {
  document.querySelectorAll(".strip-scroll-wrap").forEach((wrap) => {
    const scroller = wrap.querySelector(".strip-scroll");
    if (!scroller) return;
    const update = () => {
      const atStart = scroller.scrollLeft <= 1;
      const atEnd = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 1;
      wrap.classList.toggle("is-start", atStart);
      wrap.classList.toggle("is-end", atEnd);
    };
    scroller.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  });
})();
