// =====================================================================
// GrafoCuenta: dibuja el "vecindario" de una cuenta (lo que devuelve
// GET /analista/cuentas/{numero}/grafo) usando la libreria Cytoscape.js.
//
//   ● Cuenta (verde; ROJA si tiene alerta abierta; GRIS si esta congelada)
//   ▢ Cliente (titular)        ◆ Dispositivo (ROJO si lo comparten varios)
//   ⬡ IP                       → Transferencias (mas gruesas = mas dinero;
//                                  rojas si alguna fue retenida/bloqueada)
// Al hacer clic en una cuenta, se investiga esa cuenta.
// =====================================================================
import cytoscape from 'cytoscape'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Aviso, Girando } from '../componentes/ui'

// Formato corto para los montos en las flechas: 1.250.000 -> "$1.3M"
function corto(valor) {
  const v = Number(valor)
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`
  return `$${v}`
}

export default function GrafoCuenta({ numero, onSeleccionarCuenta, alto = 440 }) {
  const contenedor = useRef(null) // el <div> donde Cytoscape dibuja
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  // 1) Traer los datos del grafo cada vez que cambia la cuenta
  useEffect(() => {
    setDatos(null)
    setError('')
    api.get(`/analista/cuentas/${numero}/grafo`).then(setDatos).catch((e) => setError(e.message))
  }, [numero])

  // 2) Dibujar cuando llegan los datos
  useEffect(() => {
    if (!datos || !contenedor.current) return
    const oscuro = document.documentElement.classList.contains('dark')
    const transferencias = datos.aristas.filter((a) => a.tipo === 'TRANSFIERE')
    const maximo = Math.max(1, ...transferencias.map((a) => Number(a.monto)))

    const nodos = datos.nodos.map((n) => ({
      data: { ...n, label: n.etiqueta },
      classes: [
        n.tipo,
        n.central && 'central',
        n.alerta_abierta && 'alerta',
        n.estado === 'congelada' && 'congelada',
        n.compartido_con > 0 && 'compartido',
      ].filter(Boolean).join(' '),
    }))

    const aristas = datos.aristas.map((a, i) => {
      const frenada = a.estados?.some((e) => e !== 'aprobada')
      return {
        data: {
          id: `arista-${i}`,
          source: a.origen,
          target: a.destino,
          // grosor entre 1 y 8 segun el monto (escala raiz para que no se dispare)
          ancho: a.tipo === 'TRANSFIERE' ? 1 + 7 * Math.sqrt(Number(a.monto) / maximo) : 1,
          label: a.tipo === 'TRANSFIERE' ? `${a.cantidad > 1 ? a.cantidad + '× ' : ''}${corto(a.monto)}` : '',
        },
        classes: [a.tipo, frenada && 'frenada'].filter(Boolean).join(' '),
      }
    })

    const texto = oscuro ? '#BECDBB' : '#2F4A3D'
    const linea = oscuro ? '#475569' : '#BECDBB'

    const cy = cytoscape({
      container: contenedor.current,
      elements: [...nodos, ...aristas],
      wheelSensitivity: 0.2,
      style: [
        { selector: 'node', style: { label: 'data(label)', 'font-size': 9, color: texto, 'text-valign': 'bottom', 'text-margin-y': 4, 'text-wrap': 'ellipsis', 'text-max-width': 90 } },
        { selector: 'node.cuenta', style: { shape: 'ellipse', width: 26, height: 26, 'background-color': '#4D774E' } },
        { selector: 'node.cuenta.central', style: { width: 44, height: 44, 'border-width': 4, 'border-color': oscuro ? '#f8fafc' : '#0f172a', 'font-weight': 'bold', 'font-size': 11 } },
        { selector: 'node.cuenta.alerta', style: { 'background-color': '#ef4444' } },
        { selector: 'node.cuenta.congelada', style: { 'background-color': '#8FA391' } },
        { selector: 'node.cliente', style: { shape: 'round-rectangle', width: 18, height: 18, 'background-color': '#164A41' } },
        { selector: 'node.dispositivo', style: { shape: 'diamond', width: 22, height: 22, 'background-color': '#F1B24A' } },
        { selector: 'node.dispositivo.compartido', style: { width: 34, height: 34, 'background-color': '#dc2626' } },
        { selector: 'node.ip', style: { shape: 'hexagon', width: 18, height: 18, 'background-color': '#627868' } },
        { selector: 'edge', style: { width: 'data(ancho)', 'line-color': linea, 'curve-style': 'bezier', 'font-size': 8, color: texto, label: 'data(label)', 'text-rotation': 'autorotate', 'text-background-color': oscuro ? '#0f172a' : '#ffffff', 'text-background-opacity': 0.8 } },
        { selector: 'edge.TRANSFIERE', style: { 'line-color': '#9DC88D', 'target-arrow-color': '#9DC88D', 'target-arrow-shape': 'triangle' } },
        { selector: 'edge.frenada', style: { 'line-color': '#ef4444', 'target-arrow-color': '#ef4444' } },
        { selector: 'edge.TITULAR_DE', style: { 'line-style': 'dotted' } },
        { selector: 'edge.USA, edge.CONECTA_DESDE', style: { 'line-style': 'dashed', 'line-color': '#F1B24A' } },
        { selector: 'node.cuenta:active, node.cuenta:selected', style: { 'overlay-opacity': 0.15 } },
      ],
      layout: { name: 'cose', animate: false, padding: 24, nodeRepulsion: () => 9000, idealEdgeLength: () => 80 },
    })

    // Clic en una cuenta: investigarla
    cy.on('tap', 'node.cuenta', (evento) => {
      const n = evento.target.data()
      if (!n.central && onSeleccionarCuenta) onSeleccionarCuenta(n.numero)
    })
    // Cursor de "mano" sobre las cuentas
    cy.on('mouseover', 'node.cuenta', () => (contenedor.current.style.cursor = 'pointer'))
    cy.on('mouseout', 'node.cuenta', () => (contenedor.current.style.cursor = 'default'))

    return () => cy.destroy() // al cambiar de cuenta, borrar el dibujo anterior
  }, [datos])

  return (
    <div>
      {error && <Aviso>{error}</Aviso>}
      <div className="relative overflow-hidden rounded-xl bg-slate-50 ring-1 ring-slate-200" style={{ height: alto }}>
        {!datos && !error && (
          <div className="absolute inset-0 grid place-items-center text-marca-600"><Girando /></div>
        )}
        <div ref={contenedor} className="h-full w-full" />
      </div>
      <Leyenda />
    </div>
  )
}

function Leyenda() {
  const items = [
    ['bg-marca-500 rounded-full', 'Cuenta'],
    ['bg-red-500 rounded-full', 'Con alerta'],
    ['bg-slate-400 rounded-full', 'Congelada'],
    ['bg-marca-700 rounded', 'Cliente'],
    ['bg-amber-500 rotate-45', 'Dispositivo'],
    ['bg-red-600 rotate-45', 'Dispositivo compartido'],
    ['bg-slate-500 rounded-sm', 'IP'],
  ]
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      {items.map(([clase, texto]) => (
        <span key={texto} className="flex items-center gap-1.5">
          <span className={`inline-block h-2.5 w-2.5 ${clase}`} />
          {texto}
        </span>
      ))}
      <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4 bg-marca-300" />Transferencia</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4 bg-red-500" />Retenida/bloqueada</span>
    </div>
  )
}
