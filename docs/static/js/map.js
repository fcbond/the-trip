(function () {
  const el = document.getElementById("map");
  if (!el) return;

  const map = L.map(el, { scrollWheelZoom: false });

  const normal = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
  });
  const terrain = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)",
    maxZoom: 17,
  });
  // "Old Chart" reuses the normal tiles but the container gets a
  // sepia/contrast filter (see .map.layer-adventure in style.css) plus a
  // compass rose and heavier dashed route to read as an aged expedition map.
  const adventure = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
  });

  const layers = { normal, terrain, adventure };
  normal.addTo(map);

  const compass = L.DomUtil.create("img", "compass-rose");
  compass.src = el.dataset.root ? el.dataset.root + "static/img/compass-rose.svg" : "static/img/compass-rose.svg";
  compass.alt = "";
  compass.style.display = "none";
  el.appendChild(compass);

  const buttons = document.querySelectorAll(".map-layer-btn");
  let current = "normal";
  function setLayer(name) {
    map.removeLayer(layers[current]);
    layers[name].addTo(map);
    el.classList.remove("layer-" + current);
    el.classList.add("layer-" + name);
    compass.style.display = name === "adventure" ? "block" : "none";
    current = name;
    buttons.forEach((b) => {
      const active = b.dataset.layer === name;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-selected", active ? "true" : "false");
    });
  }
  buttons.forEach((b) => b.addEventListener("click", () => setLayer(b.dataset.layer)));

  fetch(el.dataset.stopsUrl)
    .then((r) => r.json())
    .then((stops) => {
      const latlngs = stops.map((s) => [s.lat, s.lon]);
      L.polyline(latlngs, {
        color: "#c1432a",
        weight: 3,
        dashArray: "1 10",
        lineCap: "round",
      }).addTo(map);

      // Each stop is marked the way it would have been on the paper map in
      // the van: a cross in pen. The slug seeds a small tilt and mirror so
      // no two crosses are identical - stable across reloads, varied across
      // the map - and each stroke is drawn twice, a paper-coloured
      // under-stroke beneath the red, so it stays legible over the dark
      // terrain tiles as well as the pale street ones.
      const hash = (str) => {
        let h = 0;
        for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
        return h;
      };
      const stopIcon = (slug, focused) => {
        const h = hash(slug);
        const size = focused ? 30 : 22;
        // Each stroke bows very slightly off true, the way a line drawn by
        // hand does - straight lines read as a multiplication sign.
        const strokes =
          '<path d="M6 5.4 Q12.9 11.3 18.2 18.8"/>' +
          '<path d="M18.4 5.8 Q11.4 12.7 5.6 18.4"/>';
        return L.divIcon({
          className: "stop-mark" + (focused ? " stop-mark--focus" : ""),
          html:
            '<svg viewBox="0 0 24 24" aria-hidden="true" style="--tilt:' +
            ((h % 17) - 8) + 'deg;--flip:' + ((h >> 5) % 2 ? -1 : 1) + '">' +
            '<g class="mark-halo">' + strokes + "</g>" +
            '<g class="mark-ink">' + strokes + "</g></svg>",
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
          popupAnchor: [0, -size / 2 - 2],
        });
      };

      const markersBySlug = {};
      stops.forEach((s) => {
        const marker = L.marker([s.lat, s.lon], {
          icon: stopIcon(s.slug, false),
          title: s.name,
          alt: "Stop: " + s.name,
          riseOnHover: true,
        }).addTo(map);
        const dates =
          s.date_start === s.date_end ? s.date_start : s.date_start + " – " + s.date_end;
        marker.bindPopup(
          '<span class="map-popup-name">' + s.name + "</span>" +
          '<span class="map-popup-date">' + dates + "</span>" +
          '<a class="map-popup-link" href="' + (el.dataset.root || "") + "stops/" + s.slug + '.html">See photos &amp; diary &rarr;</a>'
        );
        markersBySlug[s.slug] = marker;
      });

      map.fitBounds(L.latLngBounds(latlngs).pad(0.15));

      // Deep link from a photo/stop page, e.g. index.html?stop=goreme
      const focusSlug = new URLSearchParams(location.search).get("stop");
      const focusMarker = focusSlug && markersBySlug[focusSlug];
      if (focusMarker) {
        focusMarker.setIcon(stopIcon(focusSlug, true));
        map.setView(focusMarker.getLatLng(), 12);
        focusMarker.openPopup();
      }
    });
})();
