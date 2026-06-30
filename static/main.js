const API = (() => {
  const origin = window.location.origin;
  if (!origin || origin === 'null' || origin === 'file://') {
    return 'http://localhost:5000/api';
  }
  if (origin.includes('5500') || origin.includes('5501')) {
    return 'http://localhost:5000/api';
  }
  return `${origin}/api`;
})();

// Paleta para las gráficas
const COLORES = [
  '#783fa7','#817791','#ac8022','#912f2f',
  '#b49bff','#e6e6e6','#3d2955','#4346f3'
];

const DISPOSITIVOS_ES = {
  nevera: 'Nevera',
  aire_acondicionado: 'Aire Acond.',
  iluminacion: 'Iluminación',
  lavadora: 'Lavadora',
  computador: 'Computador',
  television: 'Televisión',
};

// Instancias de Chart.js
let chartPerfil = null;
let chartDiario = null;
let chartDona   = null;
let chartFranjas = null;

// ── Reloj ──────────────────────────────────────
function actualizarReloj() {
  const ahora = new Date();
  document.getElementById('topbar-clock').textContent =
    ahora.toLocaleTimeString('es-CO', { hour12: false });
}
setInterval(actualizarReloj, 1000);
actualizarReloj();

// ── Toast ──────────────────────────────────────
function toast(msg, tipo = 'success') {
  const c = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${tipo}`;
  const icono = tipo === 'success' ? '✓' : tipo === 'error' ? '✕' : '⚠';
  el.innerHTML = `<span style="color:var(--${tipo === 'success' ? 'accent' : tipo === 'error' ? 'danger' : 'warn'})">${icono}</span> ${msg}`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Fetch helper ───────────────────────────────
async function fetchAPI(endpoint) {
  const r = await fetch(`${API}${endpoint}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  if (j.status !== 'success') throw new Error(j.mensaje);
  return j.data;
}

// ── Health check ───────────────────────────────
async function checkHealth() {
  try {
    const d = await fetchAPI('/health');
    document.getElementById('status-dot').className = 'status-dot online';
    document.getElementById('status-text').textContent = 'SISTEMA ONLINE';
  } catch {
    document.getElementById('status-dot').className = 'status-dot';
    document.getElementById('status-text').textContent = 'SIN CONEXIÓN';
  }
}

// ── KPIs ───────────────────────────────────────
async function cargarResumen() {
  try {
    const d = await fetchAPI('/resumen');
    document.getElementById('kpi-kwh').textContent =
      (d.total_kwh || 0).toFixed(1);
    document.getElementById('kpi-costo').textContent =
      '$' + Math.round(d.total_costo_cop || 0).toLocaleString('es-CO');
    document.getElementById('kpi-proyeccion').textContent =
      '$' + Math.round(d.proyeccion_mensual || 0).toLocaleString('es-CO');
    document.getElementById('kpi-sobrecargas').textContent =
      d.total_sobrecargas || 0;
  } catch(e) {
    toast('Error cargando resumen: ' + e.message, 'error');
  }
}

// ── Perfil horario ─────────────────────────────
async function cargarPerfilHorario() {
  const dias = document.getElementById('sel-dias-perfil').value;
  try {
    const d = await fetchAPI(`/perfil-horario?dias=${dias}`);
    const perfil = d.perfil || [];

    // Agrupa por hora sumando todos los dispositivos
    const porHora = Array(24).fill(0);
    const conteo  = Array(24).fill(0);
    perfil.forEach(p => {
      porHora[p.hora] += p.promedio_w;
      conteo[p.hora]++;
    });
    const promedios = porHora.map((v,i) => conteo[i] ? +(v/conteo[i]).toFixed(1) : 0);

    const labels = Array.from({length:24}, (_,i) => `${String(i).padStart(2,'0')}h`);

    if (chartPerfil) chartPerfil.destroy();
    chartPerfil = new Chart(
      document.getElementById('chart-perfil').getContext('2d'),
      {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Potencia promedio (W)',
            data: promedios,
            borderColor: '#904ddd',
            backgroundColor: 'rgba(130, 49, 223, 0.08)',
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#904ddd',
            fill: true,
            tension: 0.4,
          }]
        },
        options: opcionesChart('#904ddd')
      }
    );
  } catch(e) {
    toast('Error en perfil horario: ' + e.message, 'error');
  }
}

// ── Consumo diario ─────────────────────────────
async function cargarConsumoDiario() {
  const dias = document.getElementById('sel-dias-diario').value;
  try {
    const d = await fetchAPI(`/consumo-diario?dias=${dias}`);
    const consumo = d.consumo || [];

    const fechas = [...new Set(consumo.map(r => r.fecha))].sort();
    const disps  = [...new Set(consumo.map(r => r.dispositivo))];

    const datasets = disps.map((disp, i) => ({
      label: DISPOSITIVOS_ES[disp] || disp,
      data: fechas.map(f => {
        const r = consumo.find(c => c.fecha === f && c.dispositivo === disp);
        return r ? +r.energia_kwh.toFixed(4) : 0;
      }),
      backgroundColor: COLORES[i % COLORES.length] + 'cc',
      borderColor:     COLORES[i % COLORES.length],
      borderWidth: 1,
    }));

    if (chartDiario) chartDiario.destroy();
    chartDiario = new Chart(
      document.getElementById('chart-diario').getContext('2d'),
      {
        type: 'bar',
        data: { labels: fechas, datasets },
        options: {
          ...opcionesChart(),
          scales: {
            x: { stacked: true, ...escalaX() },
            y: { stacked: true, ...escalaY() },
          }
        }
      }
    );
  } catch(e) {
    toast('Error en consumo diario: ' + e.message, 'error');
  }
}

// ── Dona: distribución costos ──────────────────
async function cargarDona() {
  try {
    const d = await fetchAPI('/dispositivos?dias=30');
    const datos = (d || []).filter(r => r.total_kwh > 0);

    if (chartDona) chartDona.destroy();
    chartDona = new Chart(
      document.getElementById('chart-dona').getContext('2d'),
      {
        type: 'doughnut',
        data: {
          labels: datos.map(r => DISPOSITIVOS_ES[r.dispositivo] || r.dispositivo),
          datasets: [{
            data: datos.map(r => +parseFloat(r.total_kwh).toFixed(2)),
            backgroundColor: COLORES.map(c => c + 'cc'),
            borderColor: COLORES,
            borderWidth: 1,
            hoverOffset: 6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: '#6b7a99',
                font: { size: 10, family: "'Space Mono'" },
                padding: 10,
                boxWidth: 10,
              }
            },
            tooltip: tooltipOpts(),
          }
        }
      }
    );
  } catch(e) {
    toast('Error en gráfica de distribución: ' + e.message, 'error');
  }
}

// ── Franjas horarias ───────────────────────────
async function cargarFranjas() {
  try {
    const d  = await fetchAPI('/costos?dias=30');
    const cs = d.costos || [];

    const franjas  = { valle: 0, normal: 0, punta: 0 };
    cs.forEach(r => {
      franjas.valle  += parseFloat(r.franja_valle  || 0);
      franjas.normal += parseFloat(r.franja_normal || 0);
      franjas.punta  += parseFloat(r.franja_punta  || 0);
    });

    if (chartFranjas) chartFranjas.destroy();
    chartFranjas = new Chart(
      document.getElementById('chart-franjas').getContext('2d'),
      {
        type: 'bar',
        data: {
          labels: ['Valle (00–06h)', 'Normal (06–18h)', 'Punta (18–24h)'],
          datasets: [{
            label: 'Costo COP',
            data: [
              Math.round(franjas.valle),
              Math.round(franjas.normal),
              Math.round(franjas.punta),
            ],
            backgroundColor: ['rgba(88, 39, 143, 0.6)','rgba(117, 0, 212, 0.6)','rgba(197, 137, 253, 0.6)'],
            borderColor:     ['#621ad6','#904ddd','#b87aff'],
            borderWidth: 1,
            borderRadius: 4,
          }]
        },
        options: {
          ...opcionesChart(),
          scales: {
            x: { ...escalaX() },
            y: { ...escalaY() },
          },
          plugins: {
            ...opcionesChart().plugins,
            legend: { display: false },
          }
        }
      }
    );
  } catch(e) {
    toast('Error en franjas: ' + e.message, 'error');
  }
}

// ── Tabla alertas ──────────────────────────────
async function cargarAlertas() {
  try {
    const d = await fetchAPI('/alertas');
    const alertas = d.alertas || [];
    document.getElementById('alertas-count').textContent = alertas.length;
    const tbody = document.getElementById('alertas-body');

    if (!alertas.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Sin alertas activas ✓</td></tr>';
      return;
    }

    tbody.innerHTML = alertas.slice(0, 8).map(a => `
      <tr>
        <td style="color:var(--text);">${DISPOSITIVOS_ES[a.dispositivo] || a.dispositivo}</td>
        <td><span class="tipo-pill tipo-${a.tipo}">${a.tipo}</span></td>
        <td style="font-family:var(--mono);color:var(--danger);">${parseFloat(a.potencia_pico).toFixed(0)} W</td>
        <td style="font-family:var(--mono);color:var(--muted);">${a.duracion_min || 0}m</td>
        <td>
          <button class="btn-resolver" onclick="resolverAlerta(${a.id}, this)">
            RESOLVER
          </button>
        </td>
      </tr>
    `).join('');
  } catch(e) {
    toast('Error cargando alertas: ' + e.message, 'error');
  }
}

async function resolverAlerta(id, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  try {
    await fetch(`${API}/alertas/${id}/resolver`, { method: 'PUT' });
    toast(`Alerta #${id} resuelta`, 'success');
    setTimeout(cargarAlertas, 800);
  } catch(e) {
    toast('Error al resolver: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = 'RESOLVER';
  }
}

// ── Tabla costos / dispositivos ────────────────
async function cargarCostosDispositivos() {
  try {
    const [disps, resumen] = await Promise.all([
      fetchAPI('/dispositivos?dias=30'),
      fetchAPI('/resumen'),
    ]);
    const riesgos = resumen.riesgo_por_dispositivo || {};
    const tbody   = document.getElementById('costos-body');

    tbody.innerHTML = (disps || []).map(d => `
      <tr>
        <td style="color:var(--text);">${DISPOSITIVOS_ES[d.dispositivo] || d.dispositivo}</td>
        <td style="font-family:var(--mono);color:var(--accent);">
          ${parseFloat(d.total_kwh || 0).toFixed(2)}
        </td>
        <td style="font-family:var(--mono);">
          $${Math.round(parseFloat(d.total_cop || 0)).toLocaleString('es-CO')}
        </td>
        <td>
          <span class="riesgo-pill riesgo-${riesgos[d.dispositivo] || 'SEGURO'}">
            ${riesgos[d.dispositivo] || 'SEGURO'}
          </span>
        </td>
      </tr>
    `).join('');
  } catch(e) {
    toast('Error cargando dispositivos: ' + e.message, 'error');
  }
}

// ── Tiempo real ────────────────────────────────
async function actualizarTiempoReal() {
  try {
    const d = await fetchAPI('/simulacion-tiempo-real');
    const list = document.getElementById('device-list');

    list.innerHTML = (d.lecturas || []).map(l => {
      const cls = l.estado === 'SOBRECARGA' ? 'sobrecarga'
                : l.estado === 'ADVERTENCIA' ? 'warn' : '';
      const badgeCls = l.estado === 'SOBRECARGA' ? 'badge-sobrecarga'
                     : l.estado === 'ADVERTENCIA' ? 'badge-warn' : 'badge-normal';
      const pct = Math.min(l.porcentaje, 100);
      return `
        <div class="device-row">
          <div class="device-row-top">
            <div class="device-name">
              ${DISPOSITIVOS_ES[l.dispositivo] || l.dispositivo}
              <span class="device-badge ${badgeCls}">${l.estado}</span>
            </div>
            <div class="device-watts">${l.potencia_w.toFixed(0)} W</div>
          </div>
          <div class="device-bar-track">
            <div class="device-bar-fill ${cls}" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    }).join('');

    document.getElementById('rt-total').textContent =
      (d.total_w || 0).toFixed(0) + ' W';
  } catch {}
}

// ── Generar nuevo reporte ──────────────────────
async function generarReporte() {
  const btn = document.getElementById('btn-generar');
  btn.disabled = true;
  btn.textContent = '⏳ PROCESANDO...';
  try {
    const r = await fetch(`${API}/generar-reporte`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dias: 7, intervalo_min: 15 }),
    });
    const j = await r.json();
    if (j.status === 'success') {
      toast(`✓ ${j.data.lecturas_nuevas.toLocaleString()} lecturas generadas`, 'success');
      setTimeout(cargarTodo, 1200);
    } else {
      toast(j.mensaje, 'error');
    }
  } catch(e) {
    toast('Error generando reporte: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ NUEVO CICLO';
  }
}

// ── Carga completa ─────────────────────────────
async function cargarTodo() {
  await checkHealth();
  await Promise.all([
    cargarResumen(),
    cargarPerfilHorario(),
    cargarConsumoDiario(),
    cargarDona(),
    cargarFranjas(),
    cargarAlertas(),
    cargarCostosDispositivos(),
    actualizarTiempoReal(),
  ]);
}

// ── Opciones base de Chart.js ──────────────────
function opcionesChart(color = '#7500d4') {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: {
        labels: {
          color: '#6b7a99',
          font: { size: 10, family: "'Space Mono'" },
          boxWidth: 10, padding: 14,
        }
      },
      tooltip: tooltipOpts(),
    },
  };
}

function escalaX() {
  return {
    ticks: { color: '#6b7a99', font: { size: 10, family: "'Space Mono'" }, maxRotation: 0 },
    grid:  { color: 'rgba(255,255,255,0.04)' },
    border:{ color: 'rgba(255,255,255,0.06)' },
  };
}

function escalaY() {
  return {
    ticks: { color: '#6b7a99', font: { size: 10, family: "'Space Mono'" } },
    grid:  { color: 'rgba(255,255,255,0.04)' },
    border:{ color: 'rgba(255,255,255,0.06)' },
  };
}

function tooltipOpts() {
  return {
    backgroundColor: '#1a2235',
    borderColor:     'rgba(255,255,255,0.1)',
    borderWidth: 1,
    titleColor: '#e8edf5',
    bodyColor:  '#6b7a99',
    titleFont:  { family: "'Space Mono'", size: 11 },
    bodyFont:   { family: "'Space Mono'", size: 10 },
    padding: 10,
    cornerRadius: 6,
  };
}

// ── Arranque ───────────────────────────────────
cargarTodo();
setInterval(actualizarTiempoReal, 5000);   // Tiempo real cada 5s
setInterval(checkHealth,          30000);  // Health cada 30s
setInterval(cargarResumen,        60000);  // KPIs cada 1 min
