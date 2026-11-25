// Detalles compartidos de index.html y simulador.html (#49, #51): la sombra de la
// barra al bajar, la aparición suave de secciones, los contadores de las cifras y
// los íconos. Todo es opcional: sin este archivo, la página se ve y funciona igual.

(function () {
  "use strict";

  // Íconos de Lucide (https://lucide.dev, licencia ISC), dibujados en línea para no
  // depender de otro servidor. Uso: <span data-icono="shuffle"></span>.
  const ICONOS = {
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    play: '<path d="M6 3 20 12 6 21Z"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    shuffle:
      '<path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22"/><path d="M2 6h1.972a4 4 0 0 1 3.6 2.2"/><path d="M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45"/>',
    "trash-2":
      '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "alert-triangle":
      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  };

  function icono(nombre) {
    const trazos = ICONOS[nombre];
    if (!trazos) return "";
    return `<svg class="icono" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${trazos}</svg>`;
  }

  function dibujarIconos(raiz = document) {
    raiz.querySelectorAll("[data-icono]:not([data-icono-listo])").forEach((el) => {
      el.insertAdjacentHTML(el.dataset.iconoLado === "fin" ? "beforeend" : "afterbegin", icono(el.dataset.icono));
      el.dataset.iconoListo = "";
    });
  }

  window.MenuCeroSitio = { icono, dibujarIconos };
  dibujarIconos();

  // Barra: borde y sombra al bajar.
  const barra = document.querySelector(".barra");
  if (barra) {
    const marcar = () => barra.classList.toggle("scrolled", window.scrollY > 40);
    marcar();
    window.addEventListener("scroll", marcar, { passive: true });
  }

  const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (quieto || !("IntersectionObserver" in window)) return;

  // Aparición suave de títulos, tarjetas y figuras.
  const aparecer = new IntersectionObserver(
    (entradas) =>
      entradas.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          aparecer.unobserve(e.target);
        }
      }),
    { threshold: 0.1 },
  );
  document
    .querySelectorAll("main section > h2, .tarjetas > .tarjeta, .metricas > div, .figuras > figure, .llamado, .panel")
    .forEach((el) => {
      const hermanos = Array.from(el.parentElement.children);
      el.style.transitionDelay = `${(hermanos.indexOf(el) % 3) * 80}ms`;
      el.classList.add("reveal");
      aparecer.observe(el);
    });

  // Contadores: solo las cifras que son un número entero.
  const contar = new IntersectionObserver(
    (entradas) =>
      entradas.forEach((e) => {
        if (!e.isIntersecting) return;
        contar.unobserve(e.target);
        const el = e.target;
        const meta = Number(el.dataset.meta);
        const inicio = performance.now();
        const paso = (t) => {
          const x = Math.min(1, (t - inicio) / 1400);
          el.textContent = Math.round(meta * (1 - Math.pow(1 - x, 3))).toLocaleString("es-MX");
          if (x < 1) requestAnimationFrame(paso);
        };
        requestAnimationFrame(paso);
      }),
    { threshold: 0.5 },
  );
  document.querySelectorAll(".cifras.pequenas .cifra").forEach((el) => {
    const texto = el.textContent.trim();
    if (!/^\d+$/.test(texto)) return;
    el.dataset.meta = texto;
    el.setAttribute("aria-label", texto);
    el.textContent = "0";
    contar.observe(el);
  });
})();
