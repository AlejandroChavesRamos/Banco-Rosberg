// =====================================================================
// Alertas: la cola de trabajo del analista de fraude.
//  - A la izquierda, la lista (se actualiza sola cada 5 segundos; las
//    alertas nuevas aparecen resaltadas).
//  - A la derecha, el detalle: por que se genero, el grafo de la cuenta y
//    los botones para decidir.
// =====================================================================
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Insignia, Tarjeta } from '../componentes/ui'
import { usePeriodico } from '../componentes/usePeriodico'
import { ESTADOS, cop, enmascarar, fechaHora } from '../formato'
import GrafoCuenta from './GrafoCuenta'

const NOMBRE_REGLA = {
  MONTO_INUSUAL: 'Monto inusual',
  VELOCIDAD: 'Velocidad',
  HORARIO_NOCTURNO: 'Horario nocturno',
  DISPOSITIVO_NUEVO: 'Dispositivo nuevo',
  CUENTA_DESTINO_NUEVA: 'Cuenta nueva',
  DISPOSITIVO_COMPARTIDO: 'Dispositivo compartido',
  CICLO_DINERO: 'Ciclo de dinero',
  CUENTA_MULA: 'Cuenta mula',
  CERCANIA_FRAUDE: 'Cerca de fraude',
  CODIGO_RETIRO_FUERZA_BRUTA: 'Fuerza bruta en retiro',
}

export function colorPuntaje(p) {
  if (p >= 70) return 'bg-red-600'
  if (p >= 40) return 'bg-amber-500'
  return 'bg-marca-500'
}

export default function Alertas() {
  const [vista, setVista] = useState('pendientes') // 'pendientes' | 'resueltas'
  const [alertas, setAlertas] = useState([])
  const [seleccionada, setSeleccionada] = useState(null)
  const [nuevas, setNuevas] = useState(new Set()) // ids que acaban de llegar
  const [barrido, setBarrido] = useState({ cargando: false, resultado: null, error: '' })
  const conocidas = useRef(null) // ids ya vistos, para detectar los nuevos

  // Revisar la lista cada 5 segundos
  async function cargar() {
    try {
      const lista = await api.get(`/analista/alertas?estado=${vista}`)
      if (vista === 'pendientes') {
        const ids = new Set(lista.map((a) => a.alerta_id))
        if (conocidas.current) {
          const recien = [...ids].filter((id) => !conocidas.current.has(id))
          if (recien.length) {
            setNuevas(new Set(recien))
            setTimeout(() => setNuevas(new Set()), 6000) // el resaltado dura 6 s
          }
        }
        conocidas.current = ids
      }
      setAlertas(lista)
      // Si la alerta abierta en el detalle ya no esta en la lista, cerrarla
      setSeleccionada((actual) => (actual ? lista.find((a) => a.alerta_id === actual.alerta_id) ?? null : null))
    } catch {
      // sin conexion momentanea: se reintenta en el siguiente ciclo
    }
  }
  usePeriodico(cargar, 5000)

  function cambiarVista(v) {
    setVista(v)
    setSeleccionada(null)
    setAlertas([])
    conocidas.current = null
  }

  // Al cambiar de pestana, recargar enseguida (sin esperar los 5 segundos)
  useEffect(() => {
    cargar()
  }, [vista])

  async function lanzarBarrido() {
    setBarrido({ cargando: true, resultado: null, error: '' })
    try {
      const r = await api.post('/analista/barrido')
      setBarrido({ cargando: false, resultado: r, error: '' })
      cargar()
    } catch (e) {
      setBarrido({ cargando: false, resultado: null, error: e.message })
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alertas de fraude</h1>
          <p className="text-sm text-slate-500">
            {vista === 'pendientes' ? 'Ordenadas por riesgo. Se actualizan solas cada 5 segundos.' : 'Decisiones ya tomadas.'}
          </p>
        </div>
        <div className="flex gap-2">
          <Boton variante="secundario" onClick={() => cambiarVista(vista === 'pendientes' ? 'resueltas' : 'pendientes')}>
            Ver {vista === 'pendientes' ? 'resueltas' : 'pendientes'}
          </Boton>
          <Boton onClick={lanzarBarrido} cargando={barrido.cargando}>Barrido del historial</Boton>
        </div>
      </div>

      <Aviso>{barrido.error}</Aviso>
      {barrido.resultado && (
        <Aviso tipo="exito">
          Barrido terminado: {barrido.resultado.total_alertas_nuevas} alerta(s) nueva(s).{' '}
          Patrones encontrados:{' '}
          {Object.entries(barrido.resultado.patrones_encontrados).map(([k, v]) => `${NOMBRE_REGLA[k] ?? k} ${v}`).join(', ') || 'ninguno'}.
        </Aviso>
      )}

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        {/* Lista */}
        <Tarjeta className="max-h-[calc(100vh-200px)] overflow-y-auto p-0">
          <div className="sticky top-0 border-b border-slate-100 bg-white px-4 py-3 text-sm font-semibold dark:border-slate-800 dark:bg-slate-900">
            {alertas.length} {vista}
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {alertas.map((a) => (
              <li key={a.alerta_id}>
                <button
                  onClick={() => setSeleccionada(a)}
                  className={`w-full px-4 py-3 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800/60 ${
                    seleccionada?.alerta_id === a.alerta_id ? 'bg-marca-50 dark:bg-marca-950/50' : ''
                  } ${nuevas.has(a.alerta_id) ? 'animate-pulse bg-red-50 dark:bg-red-950/40' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg text-xs font-bold text-white ${colorPuntaje(a.puntaje)}`}>
                      {a.puntaje}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{a.titular}</div>
                      <div className="truncate text-xs text-slate-500">
                        {enmascarar(a.cuenta)} · {a.motivos.map((m) => NOMBRE_REGLA[m.codigo] ?? m.codigo).join(', ')}
                      </div>
                    </div>
                    {nuevas.has(a.alerta_id) && <Insignia color="bg-red-600 text-white">Nueva</Insignia>}
                  </div>
                </button>
              </li>
            ))}
            {alertas.length === 0 && <li className="p-6 text-center text-sm text-slate-500">No hay alertas {vista}.</li>}
          </ul>
        </Tarjeta>

        {/* Detalle */}
        {seleccionada ? (
          <Detalle key={seleccionada.alerta_id} alerta={seleccionada} onCambio={cargar} />
        ) : (
          <Tarjeta className="grid min-h-[300px] place-items-center text-sm text-slate-500">
            Selecciona una alerta para ver el detalle y su grafo.
          </Tarjeta>
        )}
      </div>
    </div>
  )
}

function Detalle({ alerta, onCambio }) {
  const navegar = useNavigate()
  const [accion, setAccion] = useState(null) // 'fraude' | 'descartar' | 'reabrir'
  const [nota, setNota] = useState('')
  const [estado, setEstado] = useState({ cargando: false, error: '', mensaje: '' })
  const resuelta = alerta.estado === 'confirmada' || alerta.estado === 'descartada'
  const estadoTx = alerta.estado_transaccion && ESTADOS[alerta.estado_transaccion]

  async function ejecutar() {
    setEstado({ cargando: true, error: '', mensaje: '' })
    try {
      const r =
        accion === 'reabrir'
          ? await api.post(`/analista/alertas/${alerta.alerta_id}/reabrir`, { motivo: nota })
          : await api.post(`/analista/alertas/${alerta.alerta_id}/resolver`, { confirmar_fraude: accion === 'fraude', nota })
      setEstado({ cargando: false, error: '', mensaje: r.mensaje })
      setAccion(null)
      setNota('')
      onCambio()
    } catch (e) {
      setEstado({ cargando: false, error: e.message, mensaje: '' })
    }
  }

  const textos = {
    fraude: { boton: 'Confirmar: es fraude', variante: 'peligro', aviso: 'Se RECHAZA la transacción retenida (si hay) y se CONGELA la cuenta' },
    descartar: { boton: 'Confirmar: falsa alarma', variante: 'principal', aviso: 'Se APRUEBA la transacción retenida (si hay) y la alerta se cierra' },
    reabrir: { boton: 'Confirmar reapertura', variante: 'secundario', aviso: 'La alerta vuelve a la cola; lo que ya se ejecutó no se revierte solo' },
  }

  return (
    <div className="space-y-5">
      <Tarjeta className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs text-slate-500">Alerta #{alerta.alerta_id} · {fechaHora(alerta.creada_en)}</div>
            <h2 className="text-xl font-bold">{alerta.titular}</h2>
            <div className="text-sm text-slate-500">
              Cuenta {alerta.cuenta} · <span className="capitalize">{alerta.estado_cuenta}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-500">Puntaje de riesgo</div>
            <div className="text-3xl font-bold">{alerta.puntaje}<span className="text-base text-slate-400">/100</span></div>
            <div className="mt-1 h-2 w-40 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <div className={`h-full ${colorPuntaje(alerta.puntaje)}`} style={{ width: `${alerta.puntaje}%` }} />
            </div>
          </div>
        </div>

        {alerta.transaccion_id && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-slate-800/60">
            <span className="capitalize">{alerta.tipo} #{alerta.transaccion_id}</span>
            <span className="cifras font-semibold">{cop(alerta.monto)}</span>
            {estadoTx && <Insignia color={estadoTx.color}>{estadoTx.texto}</Insignia>}
          </div>
        )}

        <div>
          <h3 className="mb-2 text-sm font-semibold">¿Por qué se generó?</h3>
          <ul className="space-y-2">
            {alerta.motivos.map((m, i) => (
              <li key={i} className="flex gap-3 rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
                <span className="cifras shrink-0 rounded-md bg-red-50 px-2 py-0.5 text-xs font-bold text-red-700 dark:bg-red-950 dark:text-red-300">
                  +{m.peso}
                </span>
                <div className="text-sm">
                  <div className="font-medium">
                    {NOMBRE_REGLA[m.codigo] ?? m.codigo}
                    {m.fuente === 'barrido' && <span className="ml-2 text-xs font-normal text-slate-500">(barrido del historial)</span>}
                  </div>
                  <div className="text-slate-500">{m.detalle}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {resuelta && (
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-slate-800/60">
            <div>
              <strong>{alerta.estado === 'confirmada' ? 'Fraude confirmado' : 'Descartada (falsa alarma)'}</strong> por{' '}
              {alerta.analista ?? '—'} el {fechaHora(alerta.resuelta_en)}
            </div>
            {alerta.nota && <div className="mt-1 whitespace-pre-line text-slate-500">{alerta.nota}</div>}
          </div>
        )}

        <Aviso tipo="exito">{estado.mensaje}</Aviso>

        {/* Acciones */}
        {!accion ? (
          <div className="flex flex-wrap gap-2">
            {!resuelta ? (
              <>
                <Boton variante="peligro" onClick={() => setAccion('fraude')}>Es fraude</Boton>
                <Boton variante="secundario" onClick={() => setAccion('descartar')}>Falsa alarma</Boton>
              </>
            ) : (
              <Boton variante="secundario" onClick={() => setAccion('reabrir')}>Reabrir alerta</Boton>
            )}
            <Boton variante="secundario" onClick={() => navegar(`/intranet/investigar/${alerta.cuenta}`)}>Investigar cuenta</Boton>
          </div>
        ) : (
          // Confirmacion: repite el NOMBRE y la cuenta para evitar equivocarse de alerta
          <div className="space-y-3 rounded-xl border-2 border-dashed border-slate-300 p-4 dark:border-slate-700">
            <div className="text-sm">
              Alerta <strong>#{alerta.alerta_id}</strong> de <strong>{alerta.titular}</strong> (cuenta {enmascarar(alerta.cuenta)}).
              <div className="text-slate-500">{textos[accion].aviso}.</div>
            </div>
            <textarea
              className="w-full rounded-xl border-0 bg-white px-3 py-2 text-sm ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-marca-500 dark:bg-slate-900 dark:ring-slate-700"
              rows={2}
              placeholder={accion === 'reabrir' ? 'Motivo de la reapertura (obligatorio)' : 'Nota para la auditoría'}
              value={nota}
              onChange={(e) => setNota(e.target.value)}
            />
            <Aviso>{estado.error}</Aviso>
            <div className="flex gap-2">
              <Boton variante={textos[accion].variante} cargando={estado.cargando} onClick={ejecutar}
                     disabled={accion === 'reabrir' && nota.trim().length < 3}>
                {textos[accion].boton}
              </Boton>
              <Boton variante="secundario" onClick={() => { setAccion(null); setNota('') }}>Cancelar</Boton>
            </div>
          </div>
        )}
      </Tarjeta>

      <Tarjeta>
        <h3 className="mb-3 text-sm font-semibold">Relaciones de la cuenta</h3>
        <GrafoCuenta numero={alerta.cuenta} onSeleccionarCuenta={(n) => navegar(`/intranet/investigar/${n}`)} alto={380} />
      </Tarjeta>
    </div>
  )
}
