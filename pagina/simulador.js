// Simulador de la página de Menú Cero (#51).
//
// El usuario arma restaurantes (cocina, platillos e inventario) que se guardan en
// localStorage. «Simular», «Aleatorizar» y «Descargar en CSV» los atiende Python
// en el navegador (Pyodide): este archivo carga py/menucero-web.zip, que trae
// src/menucero, el prototipo v0 y scripts/simulador_web.py tal como están en el
// repositorio, y le pasa peticiones JSON a simulador_web.ejecutar(). El resultado
// se muestra con el mismo visor de la página principal (visor.js).
//
// La vista es un asistente: se ve un paso a la vez (restaurante, platillos,
// inventario, simular y resultados) y se avanza con «Siguiente» y «Retroceder».
// Cada paso tiene su ancla (#platillos, #resultado…), así que el botón «atrás» del
// navegador y los enlaces directos también funcionan.

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const leerJSON = (id) => JSON.parse(document.getElementById(id).textContent);

  const textoCatalogo = document.getElementById("catalogo").textContent;
  const catalogo = JSON.parse(textoCatalogo);
  const ejemplos = leerJSON("restaurantes-ejemplo");
  const config = leerJSON("config-simulador");
  const ING = catalogo.ingredientes;
  const COCINAS = catalogo.cocinas;
  const RECETAS = {};
  for (const [cocina, datos] of Object.entries(COCINAS)) {
    for (const r of datos.recetas) RECETAS[r.id] = { ...r, cocina };
  }

  const CLAVE = "menucero.simulador.v1";
  const icono = (n) => (window.MenuCeroSitio ? window.MenuCeroSitio.icono(n) : "");
  const copia = (x) => JSON.parse(JSON.stringify(x));
  const escapar = (s) =>
    String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const numero = (x, d = 2) =>
    x.toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pesos = (x) => "$" + x.toLocaleString("es-MX", { maximumFractionDigits: 0 });
  const normalizar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();

  // --- estado guardado en el navegador -----------------------------------------------

  let estado = cargar();

  function cargar() {
    try {
      const guardado = JSON.parse(localStorage.getItem(CLAVE));
      if (guardado && Array.isArray(guardado.restaurantes) && guardado.restaurantes.length) {
        guardado.activo = Math.min(Math.max(0, guardado.activo | 0), guardado.restaurantes.length - 1);
        return guardado;
      }
    } catch (e) {
      // Sin localStorage (o con datos dañados) se empieza con los ejemplos.
    }
    return { activo: 0, restaurantes: copia(ejemplos) };
  }

  function guardar() {
    try {
      localStorage.setItem(CLAVE, JSON.stringify(estado));
    } catch (e) {
      // Navegación privada o sin espacio: sigue funcionando, solo no se guarda.
    }
  }

  const actual = () => estado.restaurantes[estado.activo];

  function platillosDe(cocina) {
    const platillos = {};
    for (const r of COCINAS[cocina].recetas) {
      platillos[r.id] = { tipo: r.tipo, demanda_fija: r.demanda_fija, demanda_menu_dia: r.demanda_menu_dia };
    }
    return platillos;
  }

  function nuevoRestaurante(nombre, cocina) {
    return { nombre, cocina, platillos: platillosDe(cocina), inventario: [], dias: 7, semilla: 1, ruido: true };
  }

  // --- 1. restaurante --------------------------------------------------------------------

  const selRestaurantes = $("#sim-restaurantes");
  const inNombre = $("#sim-nombre");
  const selCocina = $("#sim-cocina");

  for (const [id, datos] of Object.entries(COCINAS)) {
    selCocina.insertAdjacentHTML("beforeend", `<option value="${id}">${escapar(datos.nombre)}</option>`);
  }

  function pintarRestaurante() {
    selRestaurantes.innerHTML = estado.restaurantes
      .map((r, k) => `<option value="${k}"${k === estado.activo ? " selected" : ""}>${escapar(r.nombre || "Sin nombre")}</option>`)
      .join("");
    const r = actual();
    inNombre.value = r.nombre;
    selCocina.value = r.cocina;
    $("#sim-borrar").disabled = estado.restaurantes.length < 2;
    $("#sim-dias").value = r.dias;
    $("#sim-semilla").value = r.semilla;
    $("#sim-ruido").checked = r.ruido;
  }

  selRestaurantes.addEventListener("change", () => {
    estado.activo = Number(selRestaurantes.value);
    guardar();
    pintarTodo();
    ocultarResultado();
  });

  inNombre.addEventListener("input", () => {
    actual().nombre = inNombre.value;
    selRestaurantes.options[estado.activo].textContent = inNombre.value || "Sin nombre";
    guardar();
  });

  selCocina.addEventListener("change", () => {
    const r = actual();
    r.cocina = selCocina.value;
    r.platillos = platillosDe(r.cocina);
    r.inventario = [];
    guardar();
    pintarTodo();
    cambiaron();
    if (python) aleatorizar("Cambió la cocina: se eligieron sus platillos y se generó un inventario al azar.");
  });

  $("#sim-nuevo").addEventListener("click", () => {
    const cocina = Object.keys(COCINAS)[0];
    estado.restaurantes.push(nuevoRestaurante(`Restaurante ${estado.restaurantes.length + 1}`, cocina));
    estado.activo = estado.restaurantes.length - 1;
    guardar();
    pintarTodo();
    ocultarResultado();
    inNombre.focus();
    inNombre.select();
    if (python) aleatorizar("Restaurante nuevo con todos los platillos de la cocina y un inventario al azar.");
  });

  $("#sim-duplicar").addEventListener("click", () => {
    const r = copia(actual());
    r.nombre = `${r.nombre} (copia)`;
    estado.restaurantes.splice(estado.activo + 1, 0, r);
    estado.activo += 1;
    guardar();
    pintarTodo();
    ocultarResultado();
  });

  $("#sim-borrar").addEventListener("click", () => {
    if (estado.restaurantes.length < 2) return;
    if (!confirm(`¿Borrar «${actual().nombre}»?`)) return;
    estado.restaurantes.splice(estado.activo, 1);
    estado.activo = Math.max(0, estado.activo - 1);
    guardar();
    pintarTodo();
    ocultarResultado();
  });

  $("#sim-restablecer").addEventListener("click", () => {
    if (!confirm("Se borran tus restaurantes y vuelven los de ejemplo. ¿Continuar?")) return;
    estado = { activo: 0, restaurantes: copia(ejemplos) };
    guardar();
    pintarTodo();
    ocultarResultado();
  });

  // --- 2. platillos --------------------------------------------------------------------------

  const cajaPlatillos = $("#sim-platillos");

  function pintarPlatillos() {
    const r = actual();
    const recetas = COCINAS[r.cocina].recetas;
    const filas = recetas.map((receta) => {
      const cfg = r.platillos[receta.id];
      const elegido = Boolean(cfg);
      const tipo = cfg ? cfg.tipo : receta.tipo;
      const fija = cfg ? cfg.demanda_fija : receta.demanda_fija;
      const menu = cfg ? cfg.demanda_menu_dia : receta.demanda_menu_dia;
      const ingredientes = Object.keys(receta.ingredientes).map((i) => ING[i].nombre.toLowerCase()).join(", ");
      return `<tr data-receta="${receta.id}"${elegido ? "" : ' class="apagado"'}>
        <td><input type="checkbox" class="casilla" data-campo="elegido" aria-label="Vender ${escapar(receta.platillo)}"${elegido ? " checked" : ""}></td>
        <td><span class="platillo">${escapar(receta.platillo)}</span><span class="ingredientes">${escapar(ingredientes)}</span></td>
        <td><select data-campo="tipo" aria-label="Tipo de ${escapar(receta.platillo)}"${elegido ? "" : " disabled"}>
          <option value="fijo"${tipo === "fijo" ? " selected" : ""}>Carta fija</option>
          <option value="secundaria"${tipo === "secundaria" ? " selected" : ""}>Solo menú del día</option>
        </select></td>
        <td class="num"><input type="number" min="0" max="500" step="1" data-campo="demanda_fija" value="${tipo === "fijo" ? fija : 0}" aria-label="Porciones al día de ${escapar(receta.platillo)}"${elegido && tipo === "fijo" ? "" : " disabled"}></td>
        <td class="num"><input type="number" min="0" max="500" step="1" data-campo="demanda_menu_dia" value="${menu}" aria-label="Porciones extra como menú del día de ${escapar(receta.platillo)}"${elegido ? "" : " disabled"}></td>
      </tr>`;
    });
    cajaPlatillos.innerHTML = `<div class="tabla"><table class="sim-tabla">
      <thead><tr><th><span class="solo-lectores">Vender</span></th><th>Platillo</th><th>Tipo</th><th class="num">Al día</th><th class="num">Menú del día</th></tr></thead>
      <tbody>${filas.join("")}</tbody></table></div>`;

    const cfgs = Object.values(r.platillos);
    const fijos = cfgs.filter((c) => c.tipo === "fijo").length;
    const porciones = cfgs.reduce((s, c) => s + (c.tipo === "fijo" ? c.demanda_fija : 0), 0);
    $("#sim-resumen-platillos").textContent =
      `${cfgs.length} de ${recetas.length} platillos: ${fijos} en la carta fija y ${cfgs.length - fijos} solo como menú del día · ${porciones} porciones al día.`;
  }

  cajaPlatillos.addEventListener("change", (e) => {
    const fila = e.target.closest("tr[data-receta]");
    if (!fila) return;
    const id = fila.dataset.receta;
    const r = actual();
    const campo = e.target.dataset.campo;
    if (campo === "elegido") {
      if (e.target.checked) {
        const base = RECETAS[id];
        r.platillos[id] = { tipo: base.tipo, demanda_fija: base.demanda_fija, demanda_menu_dia: base.demanda_menu_dia };
      } else {
        delete r.platillos[id];
      }
    } else if (campo === "tipo") {
      r.platillos[id].tipo = e.target.value;
      if (e.target.value === "fijo" && r.platillos[id].demanda_fija === 0) {
        r.platillos[id].demanda_fija = RECETAS[id].demanda_fija || 1;
      }
    } else {
      const valor = Math.round(Number(e.target.value));
      r.platillos[id][campo] = Number.isFinite(valor) ? Math.min(500, Math.max(0, valor)) : 0;
    }
    guardar();
    pintarPlatillos();
    pintarFaltan();
    cambiaron();
  });

  $("#sim-todos").addEventListener("click", () => {
    const r = actual();
    r.platillos = { ...platillosDe(r.cocina), ...r.platillos };
    guardar();
    pintarPlatillos();
    pintarFaltan();
    cambiaron();
  });

  $("#sim-ninguno").addEventListener("click", () => {
    actual().platillos = {};
    guardar();
    pintarPlatillos();
    pintarFaltan();
    cambiaron();
  });

  // --- 3. inventario ---------------------------------------------------------------------------

  const cajaInventario = $("#sim-inventario");
  const diccionario = $("#sim-diccionario");
  const porNombre = {};
  Object.entries(ING)
    .sort(([, a], [, b]) => a.nombre.localeCompare(b.nombre, "es"))
    .forEach(([id, ing]) => {
      porNombre[normalizar(ing.nombre)] = id;
      diccionario.insertAdjacentHTML(
        "beforeend",
        `<option value="${escapar(ing.nombre)}">${escapar(ing.categoria)} · ${pesos(ing.costo_kg)}/kg · dura ${ing.vida_dias[0]}–${ing.vida_dias[1]} días</option>`,
      );
    });

  function cuando(dias) {
    if (dias === 0) return "hoy";
    if (dias === 1) return "mañana";
    return `en ${dias} días`;
  }

  function pintarInventario() {
    const r = actual();
    const filas = r.inventario
      .map((fila, k) => ({ fila, k, ing: ING[fila.ingrediente] }))
      .filter((x) => x.ing)
      .sort((p, q) => p.fila.vence_en - q.fila.vence_en || p.ing.nombre.localeCompare(q.ing.nombre, "es"));

    if (filas.length === 0) {
      cajaInventario.innerHTML =
        '<p class="vacio">El inventario está vacío. Usa «Aleatorizar» o agrega ingredientes del catálogo.</p>';
    } else {
      cajaInventario.innerHTML = `<div class="tabla"><table class="sim-tabla">
        <thead><tr><th>Ingrediente</th><th>Categoría</th><th class="num">kg</th><th class="num">Vence en (días)</th><th class="num">Costo/kg</th><th class="num">Valor</th><th><span class="solo-lectores">Quitar</span></th></tr></thead>
        <tbody>${filas
          .map(({ fila, k, ing }) => {
            const urgente = fila.vence_en <= 1
              ? `<span class="urgente">${icono("alert-triangle")}vence ${cuando(fila.vence_en)}</span>`
              : "";
            return `<tr data-fila="${k}">
              <td><span class="platillo">${escapar(ing.nombre)}</span>${urgente}</td>
              <td>${escapar(ing.categoria)}</td>
              <td class="num"><input type="number" min="0" max="500" step="0.05" data-campo="cantidad_kg" value="${fila.cantidad_kg}" aria-label="kg de ${escapar(ing.nombre)}"></td>
              <td class="num"><input type="number" min="0" max="60" step="1" data-campo="vence_en" value="${fila.vence_en}" aria-label="Días para que venza ${escapar(ing.nombre)}"></td>
              <td class="num">${pesos(ing.costo_kg)}</td>
              <td class="num">${pesos(ing.costo_kg * fila.cantidad_kg)}</td>
              <td><button type="button" class="quitar" data-quitar="${k}" aria-label="Quitar ${escapar(ing.nombre)}">${icono("x")}</button></td>
            </tr>`;
          })
          .join("")}</tbody></table></div>`;
    }

    const kg = r.inventario.reduce((s, f) => s + f.cantidad_kg, 0);
    const valor = r.inventario.reduce((s, f) => s + f.cantidad_kg * (ING[f.ingrediente]?.costo_kg || 0), 0);
    const urgentes = r.inventario.filter((f) => f.vence_en <= 1).length;
    $("#sim-resumen-inventario").textContent =
      `${r.inventario.length} ingredientes · ${numero(kg, 1)} kg · ${pesos(valor)} · ${urgentes} vencen hoy o mañana.`;
    pintarFaltan();
  }

  function faltantes() {
    const r = actual();
    const hay = new Set(r.inventario.map((f) => f.ingrediente));
    const faltan = new Set();
    for (const id of Object.keys(r.platillos)) {
      for (const i of Object.keys(RECETAS[id].ingredientes)) if (!hay.has(i)) faltan.add(i);
    }
    return [...faltan];
  }

  function pintarFaltan() {
    const faltan = faltantes();
    const aviso = $("#sim-faltan");
    $("#sim-completar").disabled = faltan.length === 0;
    if (faltan.length === 0) {
      aviso.hidden = true;
      return;
    }
    const nombres = faltan.map((i) => ING[i].nombre.toLowerCase()).sort((a, b) => a.localeCompare(b, "es"));
    aviso.innerHTML = `${icono("alert-triangle")}<span>Faltan en el inventario: ${escapar(nombres.join(", "))}. Los platillos que los usan no se podrán preparar.</span>`;
    aviso.hidden = false;
  }

  function mensaje(texto) {
    const caja = $("#sim-mensaje");
    caja.textContent = texto;
    caja.hidden = !texto;
  }

  cajaInventario.addEventListener("change", (e) => {
    const fila = e.target.closest("tr[data-fila]");
    if (!fila) return;
    const item = actual().inventario[Number(fila.dataset.fila)];
    const campo = e.target.dataset.campo;
    const valor = Number(e.target.value);
    if (campo === "cantidad_kg") item.cantidad_kg = Number.isFinite(valor) ? Math.min(500, Math.max(0, Math.round(valor * 100) / 100)) : item.cantidad_kg;
    if (campo === "vence_en") item.vence_en = Number.isFinite(valor) ? Math.min(60, Math.max(0, Math.round(valor))) : item.vence_en;
    guardar();
    pintarInventario();
    cambiaron();
  });

  cajaInventario.addEventListener("click", (e) => {
    const boton = e.target.closest("[data-quitar]");
    if (!boton) return;
    const r = actual();
    const [quitado] = r.inventario.splice(Number(boton.dataset.quitar), 1);
    guardar();
    pintarInventario();
    mensaje(`Se quitó ${ING[quitado.ingrediente].nombre.toLowerCase()}.`);
    cambiaron();
  });

  $("#sim-agregar").addEventListener("submit", (e) => {
    e.preventDefault();
    const id = porNombre[normalizar($("#sim-ingrediente").value)];
    if (!id) {
      mensaje(`«${$("#sim-ingrediente").value}» no está en el catálogo. Elige uno de la lista.`);
      return;
    }
    const kg = Math.round(Number($("#sim-kg").value) * 100) / 100;
    const vence = Math.round(Number($("#sim-vence").value));
    const r = actual();
    const existente = r.inventario.find((f) => f.ingrediente === id);
    if (existente) {
      existente.cantidad_kg = kg;
      existente.vence_en = vence;
      mensaje(`${ING[id].nombre} ya estaba: se actualizó a ${numero(kg)} kg que vencen ${cuando(vence)}.`);
    } else {
      r.inventario.push({ ingrediente: id, cantidad_kg: kg, vence_en: vence });
      mensaje(`Se agregó ${ING[id].nombre.toLowerCase()}: ${numero(kg)} kg que vencen ${cuando(vence)}.`);
    }
    $("#sim-ingrediente").value = "";
    guardar();
    pintarInventario();
    cambiaron();
    $("#sim-ingrediente").focus();
  });

  // Al elegir un ingrediente, propone su compra mínima y su vida útil más corta.
  $("#sim-ingrediente").addEventListener("change", () => {
    const id = porNombre[normalizar($("#sim-ingrediente").value)];
    if (!id) return;
    $("#sim-kg").value = ING[id].compra_kg;
    $("#sim-vence").value = ING[id].vida_dias[0];
  });

  $("#sim-completar").addEventListener("click", () => {
    const faltan = faltantes();
    const r = actual();
    for (const i of faltan) {
      r.inventario.push({ ingrediente: i, cantidad_kg: ING[i].compra_kg, vence_en: ING[i].vida_dias[0] });
    }
    guardar();
    pintarInventario();
    mensaje(`Se agregaron ${faltan.length} ingredientes con su compra mínima y su vida útil más corta.`);
    cambiaron();
  });

  $("#sim-vaciar").addEventListener("click", () => {
    actual().inventario = [];
    guardar();
    pintarInventario();
    mensaje("");
    cambiaron();
  });

  $("#sim-aleatorizar").addEventListener("click", () => aleatorizar());

  function aleatorizar(texto) {
    const r = actual();
    if (Object.keys(r.platillos).length === 0) {
      mensaje("Elige al menos un platillo: el inventario al azar trae lo que usan.");
      return;
    }
    // Cada clic da otro inventario; la semilla queda en el mensaje para repetirlo.
    const semilla = Math.floor(Math.random() * 1e6);
    const respuesta = llamar({ accion: "aleatorizar", restaurante: r, semilla });
    if (!respuesta) return;
    r.inventario = respuesta.inventario;
    guardar();
    pintarInventario();
    mensaje(texto || `Inventario al azar con lo que usan los platillos elegidos (semilla ${semilla}).`);
    cambiaron();
  }

  // --- 4. simular ---------------------------------------------------------------------------------

  const botonSimular = $("#sim-simular");
  const botonCSV = $("#sim-csv");
  const botonAleatorizar = $("#sim-aleatorizar");
  const resultado = $("#sim-resultado");
  const plantillaVisor = resultado.innerHTML;
  let visor = null;
  let ultimo = null; // datos de la última simulación, para el paso 5
  let python = null;
  let vorazNombre = "";

  function hoy() {
    const d = new Date();
    const dos = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
  }

  function estadoPython(tipo, texto) {
    const caja = $("#sim-estado");
    caja.dataset.estado = tipo;
    caja.textContent = texto;
  }

  // Los errores de Python se muestran en el paso que está a la vista: en el 4, bajo
  // el estado de Python; en los demás, sobre sus botones de navegación.
  function error(texto) {
    for (const caja of document.querySelectorAll("#sim-error, .sim-bloqueo")) {
      caja.textContent = "";
      caja.hidden = true;
    }
    if (!texto) return;
    const seccion = secciones[pasoActual];
    const caja = (seccion && seccion.querySelector(".sim-bloqueo")) || $("#sim-error");
    caja.textContent = texto;
    caja.hidden = false;
  }

  function llamar(peticion) {
    if (!python) return null;
    const respuesta = JSON.parse(python.ejecutar(JSON.stringify(peticion)));
    if (!respuesta.ok) {
      error(respuesta.error);
      return null;
    }
    error("");
    return respuesta;
  }

  for (const [sel, campo] of [["#sim-dias", "dias"], ["#sim-semilla", "semilla"]]) {
    $(sel).addEventListener("change", (e) => {
      const r = actual();
      const valor = Math.round(Number(e.target.value));
      const [min, max] = [Number(e.target.min), Number(e.target.max)];
      r[campo] = Number.isFinite(valor) ? Math.min(max, Math.max(min, valor)) : r[campo];
      e.target.value = r[campo];
      guardar();
      cambiaron();
    });
  }
  $("#sim-ruido").addEventListener("change", (e) => {
    actual().ruido = e.target.checked;
    guardar();
    cambiaron();
  });

  function ocultarResultado() {
    if (visor) visor.destruir();
    visor = null;
    ultimo = null;
    resultado.hidden = true;
    $("#sim-desactualizado").hidden = true;
    $("#sim-resumen-resultado").textContent = "Todavía no hay resultados: arma el restaurante y pulsa «Simular».";
    resultado.innerHTML = plantillaVisor;
    error("");
    mensaje("");
    if (python) estadoPython("listo", `Listo para simular con el ${vorazNombre}.`);
    if (secciones.length) pintarGuia();
  }

  function cambiaron() {
    if (!ultimo) return;
    $("#sim-desactualizado").hidden = false;
    if (python) estadoPython("listo", "Cambiaste los datos: vuelve a simular para ver el resultado nuevo.");
  }

  botonSimular.addEventListener("click", () => {
    estadoPython("cargando", "Simulando…");
    botonSimular.disabled = true;
    // Deja que el navegador pinte «Simulando…» antes de ocupar el hilo con Python.
    setTimeout(() => {
      const inicio = performance.now();
      const datos = llamar({ accion: "simular", restaurante: actual(), hoy: hoy() });
      const ms = performance.now() - inicio;
      botonSimular.disabled = false;
      if (!datos) {
        estadoPython("error", "No se pudo simular: revisa el mensaje de abajo.");
        return;
      }
      if (visor) visor.destruir();
      ultimo = datos;
      const listo = `${datos.fechas.length} días de A y B con el ${datos.voraz}, en ${numero(ms / 1000, 2)} s.`;
      estadoPython("listo", `Listo: ${listo}`);
      $("#sim-resumen-resultado").textContent = `${actual().nombre || "Sin nombre"}: ${listo}`;
      $("#sim-desactualizado").hidden = true;
      // Primero se muestra el paso 5: el visor mide el ancho de la gráfica al montarse.
      irA(indiceDe("resultado"));
      resultado.innerHTML = plantillaVisor;
      resultado.hidden = false;
      visor = window.MenuCeroVisor.montar(resultado.querySelector(".visor"), datos);
    }, 30);
  });

  botonCSV.addEventListener("click", () => {
    const respuesta = llamar({ accion: "csv", restaurante: actual(), hoy: hoy() });
    if (!respuesta) return;
    const bytes = Uint8Array.from(atob(respuesta.zip), (c) => c.charCodeAt(0));
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
    const base = normalizar(actual().nombre).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "restaurante";
    enlace.download = `${base}.zip`;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  });

  // --- Python en el navegador -----------------------------------------------------------------------

  function cargarScript(src) {
    return new Promise((resolver, fallar) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolver;
      s.onerror = () => fallar(new Error(`No se pudo descargar ${src}`));
      document.head.appendChild(s);
    });
  }

  async function iniciarPython() {
    const base = `https://cdn.jsdelivr.net/pyodide/v${config.pyodide}/full/`;
    estadoPython("cargando", "Cargando Python en el navegador… la primera vez tarda unos segundos.");
    try {
      await cargarScript(base + "pyodide.js");
      const pyodide = await window.loadPyodide({ indexURL: base });
      const respuesta = await fetch(config.paquete);
      if (!respuesta.ok) throw new Error(`No se pudo descargar ${config.paquete}`);
      pyodide.unpackArchive(await respuesta.arrayBuffer(), "zip", { extractDir: "/home/pyodide/menucero" });
      pyodide.runPython(
        'import sys\nsys.path[:0] = ["/home/pyodide/menucero/src", "/home/pyodide/menucero/scripts"]',
      );
      const puente = pyodide.pyimport("simulador_web");
      vorazNombre = puente.iniciar(textoCatalogo);
      python = { ejecutar: (texto) => puente.ejecutar(texto) };
    } catch (e) {
      estadoPython("error", "No se pudo cargar Python en este navegador. Revisa tu conexión y recarga la página.");
      error(String(e.message || e));
      return;
    }
    botonSimular.disabled = false;
    botonCSV.disabled = false;
    botonAleatorizar.disabled = false;
    estadoPython("listo", `Listo para simular con el ${vorazNombre}.`);
  }

  // --- pasos: uno a la vez, con «Retroceder» y «Siguiente» ---------------------------------------------

  const secciones = [...document.querySelectorAll("main section[data-paso]")];
  const guia = $("#sim-guia");
  const enlacesGuia = [...guia.querySelectorAll("a[href^='#']")];
  let pasoActual = -1;

  const indiceDe = (id) => secciones.findIndex((s) => s.id === id);

  // Lo que impide pasar al siguiente paso; vacío si se puede.
  function faltaAlgo(i) {
    const r = actual();
    if (secciones[i].id === "platillos" && !Object.keys(r.platillos).length) {
      return "Elige al menos un platillo para seguir.";
    }
    if (secciones[i].id === "inventario" && !r.inventario.length) {
      return "Agrega al menos un ingrediente, o usa «Aleatorizar», para seguir.";
    }
    return "";
  }

  function pintarGuia() {
    enlacesGuia.forEach((a, k) => {
      if (k === pasoActual) a.setAttribute("aria-current", "step");
      else a.removeAttribute("aria-current");
      a.classList.toggle("hecho", k < pasoActual);
      const bloqueado = secciones[k].id === "resultado" && !ultimo;
      a.setAttribute("aria-disabled", String(bloqueado));
      a.title = bloqueado ? "Primero simula en el paso 4" : "";
    });
    const titulo = secciones[pasoActual].querySelector("h2").textContent;
    $("#sim-progreso").textContent = `Paso ${pasoActual + 1} de ${secciones.length} · ${titulo}`;
  }

  // Muestra el paso i (sin resultados, el 5 manda al 4) y devuelve el que quedó.
  function mostrar(i, { mover = true } = {}) {
    if (secciones[i].id === "resultado" && !ultimo) i = indiceDe("simular");
    const cambio = i !== pasoActual;
    pasoActual = i;
    secciones.forEach((s, k) => {
      s.hidden = k !== i;
    });
    error("");
    pintarGuia();
    if (cambio && mover) {
      guia.scrollIntoView({ block: "start" });
      secciones[i].querySelector("h2").focus({ preventScroll: true });
    }
    // Si el visor se dibujó mientras estaba oculto, vuelve a medir la gráfica.
    if (cambio && secciones[i].id === "resultado") window.dispatchEvent(new Event("resize"));
    return i;
  }

  function irA(i) {
    const quedo = mostrar(Math.min(secciones.length - 1, Math.max(0, i)));
    const ancla = "#" + secciones[quedo].id;
    if (location.hash !== ancla) history.pushState(null, "", ancla);
  }

  function sincronizar(opciones) {
    const quedo = mostrar(Math.max(0, indiceDe(decodeURIComponent(location.hash.slice(1)))), opciones);
    const ancla = "#" + secciones[quedo].id;
    if (location.hash && location.hash !== ancla) history.replaceState(null, "", ancla);
  }

  guia.addEventListener("click", (e) => {
    const a = e.target.closest("a[href^='#']");
    if (!a) return;
    e.preventDefault();
    if (a.getAttribute("aria-disabled") === "true") return;
    irA(enlacesGuia.indexOf(a));
  });

  for (const nav of document.querySelectorAll(".sim-navegacion")) {
    nav.addEventListener("click", (e) => {
      const boton = e.target.closest("[data-ir]");
      if (!boton) return;
      const i = secciones.indexOf(boton.closest("section[data-paso]"));
      if (boton.dataset.ir === "anterior") irA(i - 1);
      else if (boton.dataset.ir === "inicio") irA(0);
      else if (boton.dataset.ir === "siguiente") {
        const falta = faltaAlgo(i);
        if (falta) error(falta);
        else irA(i + 1);
      }
    });
    nav.hidden = false;
  }

  for (const s of secciones) s.querySelector("h2").tabIndex = -1;
  window.addEventListener("popstate", () => sincronizar());
  window.addEventListener("hashchange", () => sincronizar());
  guia.hidden = false;
  sincronizar({ mover: false });

  // --- arranque -------------------------------------------------------------------------------------

  function pintarTodo() {
    pintarRestaurante();
    pintarPlatillos();
    pintarInventario();
  }

  botonAleatorizar.disabled = true;
  pintarTodo();
  iniciarPython();
})();
