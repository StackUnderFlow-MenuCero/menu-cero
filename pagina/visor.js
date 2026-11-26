// Visor día por día de la página de Menú Cero (#49).
// Reproduce una corrida del simulador real (src/menucero/simulacion.py) que
// scripts/pagina.py guarda en <script id="datos-visor">. No calcula la
// simulación: solo la muestra día por día y suma lo acumulado.

(function () {
  "use strict";

  const raiz = document.getElementById("visor");
  const fuente = document.getElementById("datos-visor");
  if (!raiz || !fuente) return;

  const datos = JSON.parse(fuente.textContent);
  const dias = datos.fechas.length;
  const $ = (sel) => raiz.querySelector(sel);
  const svgNS = "http://www.w3.org/2000/svg";

  const kg = (x, d = 1) =>
    x.toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pesos = (x) => "$" + x.toLocaleString("es-MX", { maximumFractionDigits: 0 });
  const suma = (xs) => xs.reduce((a, b) => a + b, 0);
  const escapar = (s) =>
    String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  let escenario = datos.escenarios[0];
  let dia = 1; // 1 = el primer día
  let reloj = null;

  // --- totales acumulados -----------------------------------------------------

  function acumulado(lado, hasta) {
    const ings = escenario.ingredientes;
    let total = 0;
    let costo = 0;
    for (let t = 0; t < hasta; t++) {
      escenario[lado][t].merma.forEach((m, i) => {
        total += m;
        costo += m * ings[i].costo;
      });
    }
    return { kg: total, costo };
  }

  // --- controles --------------------------------------------------------------

  const grupo = $(".visor-escenarios");
  datos.escenarios.forEach((e, k) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = e.nombre;
    b.setAttribute("aria-pressed", k === 0 ? "true" : "false");
    b.addEventListener("click", () => {
      escenario = e;
      grupo.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      pintar();
    });
    grupo.appendChild(b);
  });

  const rango = $(".visor-rango");
  rango.max = String(dias);
  rango.addEventListener("input", () => irA(Number(rango.value)));
  $(".visor-anterior").addEventListener("click", () => irA(dia - 1));
  $(".visor-siguiente").addEventListener("click", () => irA(dia + 1));

  const boton = $(".visor-reproducir");
  boton.addEventListener("click", () => (reloj ? detener() : reproducir()));

  function reproducir() {
    if (dia === dias) irA(1);
    boton.textContent = "Pausar";
    boton.setAttribute("aria-pressed", "true");
    reloj = setInterval(() => {
      if (dia >= dias) return detener();
      irA(dia + 1);
    }, 1600);
  }

  function detener() {
    clearInterval(reloj);
    reloj = null;
    boton.textContent = "Reproducir";
    boton.setAttribute("aria-pressed", "false");
  }

  function irA(t) {
    dia = Math.min(dias, Math.max(1, t));
    pintar();
  }

  // --- gráfica de merma acumulada -----------------------------------------------

  const grafica = $(".visor-grafica");
  const ayuda = $(".visor-ayuda");
  // Se dibuja al ancho real del contenedor para que el texto quede en px reales.
  let ANCHO = 640;
  let ALTO = 260;
  const M = { arriba: 16, derecha: 92, abajo: 34, izquierda: 44 };

  function el(nombre, attrs, padre) {
    const n = document.createElementNS(svgNS, nombre);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (padre) padre.appendChild(n);
    return n;
  }

  function dibujarGrafica() {
    ANCHO = Math.max(300, Math.round(grafica.clientWidth || 640));
    const angosta = ANCHO < 520;
    ALTO = angosta ? 220 : 260;
    M.derecha = angosta ? 76 : 92;
    const serie = (lado) => Array.from({ length: dias }, (_, t) => acumulado(lado, t + 1).kg);
    const a = serie("A");
    const b = serie("B");
    const maximo = Math.max(...a, ...b, 1);
    const paso = maximo > 60 ? 20 : maximo > 30 ? 10 : 5;
    const tope = Math.ceil(maximo / paso) * paso;
    const ancho = ANCHO - M.izquierda - M.derecha;
    const alto = ALTO - M.arriba - M.abajo;
    const x = (t) => M.izquierda + (dias === 1 ? ancho / 2 : (t * ancho) / (dias - 1));
    const y = (v) => M.arriba + alto - (v / tope) * alto;

    grafica.replaceChildren();
    const svg = el("svg", {
      viewBox: `0 0 ${ANCHO} ${ALTO}`,
      width: ANCHO,
      height: ALTO,
      role: "img",
      "aria-label": `Merma acumulada en ${escenario.nombre}: al final, A ${kg(a[dias - 1])} kg y B ${kg(b[dias - 1])} kg.`,
    }, grafica);

    for (let v = 0; v <= tope; v += paso) {
      el("line", { x1: M.izquierda, x2: ANCHO - M.derecha, y1: y(v), y2: y(v), class: "rejilla" }, svg);
      el("text", { x: M.izquierda - 8, y: y(v) + 4, class: "eje", "text-anchor": "end" }, svg).textContent = v;
    }
    el("text", { x: 12, y: M.arriba + alto / 2, class: "eje", transform: `rotate(-90 12 ${M.arriba + alto / 2})`, "text-anchor": "middle" }, svg).textContent = "kg";
    datos.fechas.forEach((f, t) => {
      const texto = angosta ? String(t + 1) : `Día ${t + 1}`;
      el("text", { x: x(t), y: ALTO - 10, class: "eje" + (t + 1 === dia ? " eje-actual" : ""), "text-anchor": "middle" }, svg).textContent = texto;
    });

    el("line", { x1: x(dia - 1), x2: x(dia - 1), y1: M.arriba, y2: M.arriba + alto, class: "guia" }, svg);

    [["A", a], ["B", b]].forEach(([lado, valores]) => {
      const puntos = valores.map((v, t) => `${x(t)},${y(v)}`).join(" ");
      el("polyline", { points: puntos, class: `linea linea-${lado.toLowerCase()}` }, svg);
      valores.forEach((v, t) => {
        el("circle", { cx: x(t), cy: y(v), r: t + 1 === dia ? 6 : 4, class: `punto punto-${lado.toLowerCase()}` }, svg);
      });
    });

    // Etiquetas directas al final de cada línea, separadas si se enciman.
    let ya = y(a[dias - 1]);
    let yb = y(b[dias - 1]);
    if (Math.abs(ya - yb) < 16) {
      const centro = (ya + yb) / 2;
      ya = centro - 8;
      yb = centro + 8;
    }
    el("text", { x: ANCHO - M.derecha + 10, y: ya + 4, class: "etiqueta" }, svg).textContent = `A · ${kg(a[dias - 1])} kg`;
    el("text", { x: ANCHO - M.derecha + 10, y: yb + 4, class: "etiqueta" }, svg).textContent = `B · ${kg(b[dias - 1])} kg`;

    // Zonas de cada día: más anchas que los puntos, para el cursor y el clic.
    const banda = dias === 1 ? ancho : ancho / (dias - 1);
    datos.fechas.forEach((f, t) => {
      const zona = el("rect", { x: x(t) - banda / 2, y: M.arriba, width: banda, height: alto, class: "zona" }, svg);
      const texto = `Día ${t + 1} · ${f}: A ${kg(a[t])} kg, B ${kg(b[t])} kg acumulados`;
      zona.addEventListener("mouseenter", () => mostrarAyuda(texto, x(t), Math.min(y(a[t]), y(b[t]))));
      zona.addEventListener("mouseleave", () => (ayuda.hidden = true));
      zona.addEventListener("click", () => irA(t + 1));
    });
  }

  function mostrarAyuda(texto, px, py) {
    ayuda.textContent = texto;
    ayuda.hidden = false;
    const caja = grafica.getBoundingClientRect();
    const escala = caja.width / ANCHO;
    const izquierda = Math.min(Math.max(px * escala - ayuda.offsetWidth / 2, 0), caja.width - ayuda.offsetWidth);
    ayuda.style.left = `${izquierda}px`;
    ayuda.style.top = `${Math.max(py * escala - ayuda.offsetHeight - 12, 0)}px`;
  }

  // --- paneles del día ----------------------------------------------------------

  function pintarCifras() {
    const a = acumulado("A", dia);
    const b = acumulado("B", dia);
    $(".visor-a").textContent = `${kg(a.kg)} kg`;
    $(".visor-a-costo").textContent = `${pesos(a.costo)} en ingredientes tirados`;
    $(".visor-b").textContent = `${kg(b.kg)} kg`;
    $(".visor-b-costo").textContent = `${pesos(b.costo)} en ingredientes tirados`;
    const evitado = a.kg > 0 ? (100 * (a.kg - b.kg)) / a.kg : null;
    $(".visor-evitado").textContent = evitado === null ? "—" : `${kg(evitado)} %`;
    $(".visor-ahorro").textContent =
      evitado === null ? "Todavía no hay merma en A" : `${pesos(a.costo - b.costo)} ahorrados hasta hoy`;
  }

  function pintarMenu() {
    const hoy = escenario.B[dia - 1];
    const lista = $(".visor-menu");
    const platillos = Object.entries(hoy.menu);
    if (platillos.length === 0) {
      lista.innerHTML =
        '<p class="vacio">Hoy el voraz no propuso menú del día: no quedan ingredientes en riesgo que alguna receta pueda aprovechar.</p>';
    } else {
      lista.innerHTML =
        "<ul>" +
        platillos
          .map(([id, n]) => {
            const vendidas = hoy.vendidas[id] || 0;
            return `<li><span>${escapar(escenario.recetas[id] || id)}</span><span class="num">${vendidas} de ${n} vendidas</span></li>`;
          })
          .join("") +
        "</ul>";
    }
    const fa = escenario.A[dia - 1];
    $(".visor-fijo").textContent =
      `Menú fijo servido: A ${fa.fijas} y B ${hoy.fijas} porciones. ` +
      `Sin atender por falta de ingredientes: A ${fa.no_atendidas} y B ${hoy.no_atendidas}.`;
  }

  function pintarMerma() {
    const ma = escenario.A[dia - 1].merma;
    const mb = escenario.B[dia - 1].merma;
    const filas = escenario.ingredientes
      .map((ing, i) => ({ ing, a: ma[i], b: mb[i] }))
      .filter((f) => f.a > 0.0005 || f.b > 0.0005)
      .sort((p, q) => q.a + q.b - (p.a + p.b));
    const caja = $(".visor-merma");
    if (filas.length === 0) {
      caja.innerHTML = '<p class="vacio">Hoy no se tiró nada en A ni en B.</p>';
      return;
    }
    caja.innerHTML = tabla(
      ["Ingrediente", "A (kg)", "B (kg)"],
      filas.map((f) => [escapar(f.ing.nombre), kg(f.a, 2), kg(f.b, 2)]),
      `<tr><td>Total</td><td class="num">${kg(suma(ma), 2)}</td><td class="num">${kg(suma(mb), 2)}</td></tr>`,
    );
  }

  function cuando(vence) {
    if (vence < dia) return "ya caducado";
    if (vence === dia) return "hoy";
    if (vence === dia + 1) return "mañana";
    return `en ${vence - dia} días`;
  }

  function pintarPorVencer() {
    const sa = escenario.A[dia - 1].stock;
    const sb = escenario.B[dia - 1].stock;
    const filas = escenario.ingredientes
      .map((ing, i) => ({ ing, a: sa[i], b: sb[i] }))
      .filter((f) => f.ing.vence <= dia + 2 && (f.a > 0.0005 || f.b > 0.0005))
      .sort((p, q) => p.ing.vence - q.ing.vence || q.a - p.a);
    const caja = $(".visor-por-vencer");
    if (filas.length === 0) {
      caja.innerHTML = '<p class="vacio">No queda nada que venza en los próximos 3 días.</p>';
      return;
    }
    caja.innerHTML = tabla(
      ["Ingrediente", "Vence", "Queda en A (kg)", "Queda en B (kg)"],
      filas.map((f) => [escapar(f.ing.nombre), cuando(f.ing.vence), kg(f.a, 2), kg(f.b, 2)]),
    );
  }

  function tabla(columnas, filas, pie = "") {
    const num = (k) => (k >= columnas.length - 2 ? ' class="num"' : "");
    return (
      '<div class="tabla"><table><thead><tr>' +
      columnas.map((c, k) => `<th${num(k)}>${c}</th>`).join("") +
      "</tr></thead><tbody>" +
      filas.map((f) => "<tr>" + f.map((v, k) => `<td${num(k)}>${v}</td>`).join("") + "</tr>").join("") +
      pie +
      "</tbody></table></div>"
    );
  }

  // --- todo junto ---------------------------------------------------------------

  function pintar() {
    rango.value = String(dia);
    $(".visor-dia").textContent = `Día ${dia} de ${dias} · ${datos.fechas[dia - 1]}`;
    $(".visor-anterior").disabled = dia === 1;
    $(".visor-siguiente").disabled = dia === dias;
    $(".visor-descripcion").textContent = escenario.descripcion;
    pintarCifras();
    dibujarGrafica();
    pintarMenu();
    pintarMerma();
    pintarPorVencer();
    const a = acumulado("A", dia).kg;
    const b = acumulado("B", dia).kg;
    $(".visor-anuncio").textContent =
      `${escenario.nombre}, día ${dia}: merma acumulada A ${kg(a)} kg, B ${kg(b)} kg.`;
  }

  // Enlace directo a una situación y un día: ?escenario=examenes&dia=3
  const pedido = new URLSearchParams(location.search);
  const elegido = datos.escenarios.findIndex((e) => e.id === pedido.get("escenario"));
  if (elegido >= 0) grupo.querySelectorAll("button")[elegido].click();
  if (pedido.has("dia")) dia = Math.min(dias, Math.max(1, Number(pedido.get("dia")) || 1));

  raiz.hidden = false;
  pintar();

  let espera = null;
  window.addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(dibujarGrafica, 150);
  });
})();
