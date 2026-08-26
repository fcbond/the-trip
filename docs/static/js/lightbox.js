(function () {
  const box = document.getElementById("lightbox");
  if (!box) return;
  const img = document.getElementById("lightbox-img");
  const caption = document.getElementById("lightbox-caption");
  const closeBtn = document.getElementById("lightbox-close");
  const prevBtn = document.getElementById("lightbox-prev");
  const nextBtn = document.getElementById("lightbox-next");

  let slides = [];
  let index = -1;

  function open(i) {
    index = i;
    const s = slides[index];
    img.src = s.dataset.full;
    img.alt = s.dataset.caption || "";
    caption.textContent = s.dataset.id + " — " + (s.dataset.caption || "");
    box.hidden = false;
    prevBtn.style.visibility = slides.length > 1 ? "visible" : "hidden";
    nextBtn.style.visibility = slides.length > 1 ? "visible" : "hidden";
  }

  function close() {
    box.hidden = true;
    img.src = "";
  }

  function step(delta) {
    if (!slides.length) return;
    open((index + delta + slides.length) % slides.length);
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("a")) return; // let real links (e.g. photo id, cross-references) navigate normally
    const trigger = e.target.closest("[data-lightbox]");
    if (!trigger) return;
    slides = Array.from(document.querySelectorAll("[data-lightbox]"));
    open(slides.indexOf(trigger));
  });

  document.addEventListener("keydown", (e) => {
    const trigger = document.activeElement && document.activeElement.closest && document.activeElement.closest("[data-lightbox]");
    if (trigger && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      slides = Array.from(document.querySelectorAll("[data-lightbox]"));
      open(slides.indexOf(trigger));
      return;
    }
    if (box.hidden) return;
    if (e.key === "Escape") close();
    if (e.key === "ArrowLeft") step(-1);
    if (e.key === "ArrowRight") step(1);
  });

  closeBtn.addEventListener("click", close);
  prevBtn.addEventListener("click", () => step(-1));
  nextBtn.addEventListener("click", () => step(1));
  box.addEventListener("click", (e) => {
    if (e.target === box) close();
  });
})();
