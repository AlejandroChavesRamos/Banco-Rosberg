// =====================================================================
// Chat.jsx - Piezas comunes de las conversaciones tipo messenger.
//
//   useConversacion(ruta)  trae una conversacion y pregunta cada 3 segundos
//                          si hay mensajes nuevos (?despues_de=<ultimo id>),
//                          asi solo viajan los mensajes que faltan.
//   <Mensajes>             las burbujas, agrupadas por dia
//   <Redactar>             la caja para escribir (Enter envia, Shift+Enter
//                          hace un salto de linea)
//   <Estrellas>            calificacion de 1 a 5
// =====================================================================
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icono from './Icono'
import { Boton, Girando } from './ui'
import { usePeriodico } from './usePeriodico'

const INTERVALO_MS = 3000

export function useConversacion(ruta) {
  const [tiquete, setTiquete] = useState(null)
  const [mensajes, setMensajes] = useState([])
  const [error, setError] = useState('')
  const ultimoId = useRef(0)
  const rutaActual = useRef(ruta)
  const pidiendo = useRef(false)

  // Al cambiar de conversacion, empezar de cero
  useEffect(() => {
    rutaActual.current = ruta
    ultimoId.current = 0
    setTiquete(null)
    setMensajes([])
    setError('')
  }, [ruta])

  const actualizar = useCallback(async () => {
    if (!ruta || pidiendo.current) return
    pidiendo.current = true
    const pedida = ruta
    try {
      const r = await api.get(`${pedida}?despues_de=${ultimoId.current}`)
      if (rutaActual.current !== pedida) return // la persona ya abrio otra conversacion
      setTiquete(r.tiquete)
      if (r.mensajes.length) {
        ultimoId.current = r.mensajes[r.mensajes.length - 1].id
        setMensajes((previos) => [...previos, ...r.mensajes.filter((m) => !previos.some((p) => p.id === m.id))])
      }
      setError('')
    } catch (e) {
      if (rutaActual.current === pedida) setError(e.message)
    } finally {
      pidiendo.current = false
    }
  }, [ruta])

  usePeriodico(actualizar, INTERVALO_MS)
  useEffect(() => { actualizar() }, [actualizar])

  return { tiquete, setTiquete, mensajes, error, actualizar }
}

function dia(texto) {
  const f = new Date(texto)
  const hoy = new Date()
  const ayer = new Date()
  ayer.setDate(hoy.getDate() - 1)
  if (f.toDateString() === hoy.toDateString()) return 'Hoy'
  if (f.toDateString() === ayer.toDateString()) return 'Ayer'
  return f.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })
}

function hora(texto) {
  return new Date(texto).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' })
}

// Burbujas. Cada mensaje: { id, texto, creado_en, mio, autor, estado? }
// "pie" permite agregar algo debajo de una burbuja (por ejemplo, el estado del correo).
// "onOpcion": si se pasa, los botones de respuesta rapida del ULTIMO mensaje
// del asistente se pueden pulsar (envian ese texto).
export function Mensajes({ mensajes, cargando, vacio, pie, onOpcion }) {
  const [enviando, setEnviando] = useState(null)
  async function elegir(texto) {
    setEnviando(texto)
    try { await onOpcion(texto) } finally { setEnviando(null) }
  }
  const caja = useRef(null)
  const pegadoAbajo = useRef(true)

  // Si la persona esta leyendo mensajes viejos, no la movemos; si esta abajo, seguimos el chat
  function alDesplazar() {
    const c = caja.current
    pegadoAbajo.current = c.scrollHeight - c.scrollTop - c.clientHeight < 80
  }
  useLayoutEffect(() => {
    if (pegadoAbajo.current && caja.current) caja.current.scrollTop = caja.current.scrollHeight
  }, [mensajes.length])

  let diaAnterior = null
  return (
    <div ref={caja} onScroll={alDesplazar} className="flex-1 space-y-1 overflow-y-auto bg-marca-50/40 px-4 py-5 sm:px-6"
         role="log" aria-live="polite" aria-label="Mensajes de la conversación">
      {cargando && <div className="flex justify-center py-10 text-marca-500"><Girando /></div>}
      {!cargando && mensajes.length === 0 && vacio}
      {mensajes.map((m, i) => {
        const d = dia(m.creado_en)
        const separador = d !== diaAnterior
        diaAnterior = d
        // El nombre solo se muestra en el primer mensaje de una racha del otro lado
        const anterior = mensajes[i - 1]
        const mostrarAutor = !m.mio && (separador || !anterior || anterior.mio || anterior.autor !== m.autor)
        const bot = m.de === 'asistente'
        return (
          <div key={m.id}>
            {separador && (
              <div className="my-4 text-center text-xs font-medium capitalize text-marca-500">{d}</div>
            )}
            <div className={`flex ${m.mio ? 'justify-end' : 'justify-start'} ${mostrarAutor ? 'mt-3' : ''}`}>
              <div className="max-w-[80%] sm:max-w-[70%]">
                {mostrarAutor && (
                  <div className="mb-1 ml-3 flex items-center gap-1 text-xs font-semibold text-marca-600">
                    {bot && <Icono nombre="robot" className="h-3.5 w-3.5" />}
                    {m.autor}
                  </div>
                )}
                <div className={`whitespace-pre-line break-words rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                  m.mio ? 'rounded-br-md bg-marca-700 text-white'
                    : bot ? 'rounded-bl-md bg-oro-claro/40 text-marca-900 ring-1 ring-oro/40'
                      : 'rounded-bl-md bg-white text-marca-900 ring-1 ring-marca-100'
                }`}>
                  {m.texto}
                  <div className={`mt-1 text-right text-[11px] ${m.mio ? 'text-white/70' : 'text-slate-400'}`}>
                    {hora(m.creado_en)}
                  </div>
                </div>
                {pie?.(m)}
                {onOpcion && bot && i === mensajes.length - 1 && m.opciones?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Respuestas rápidas">
                    {m.opciones.map((o) => (
                      <button key={o} type="button" disabled={Boolean(enviando)} onClick={() => elegir(o)}
                              className={`rounded-full px-3.5 py-1.5 text-sm font-medium ring-1 transition-colors disabled:opacity-50 ${
                                o === 'Hablar con un asesor'
                                  ? 'bg-white text-marca-600 ring-marca-200 hover:bg-marca-50'
                                  : 'bg-marca-700 text-white ring-marca-700 hover:bg-marca-800'
                              }`}>
                        {enviando === o ? '…' : o}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Caja para escribir
export function Redactar({ onEnviar, deshabilitado, motivo, placeholder = 'Escribe un mensaje', maximo = 1000, textoBoton = 'Enviar' }) {
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const area = useRef(null)

  // El cuadro crece con el texto (hasta unas 6 lineas)
  useLayoutEffect(() => {
    const a = area.current
    if (!a) return
    if (!texto) { a.style.height = ''; return } // vacio: una sola linea, aunque el texto de ayuda sea largo
    a.style.height = 'auto'
    a.style.height = `${Math.min(a.scrollHeight, 160)}px`
  }, [texto])

  async function enviar(e) {
    e?.preventDefault()
    const limpio = texto.trim()
    if (!limpio || enviando) return
    setEnviando(true)
    setError('')
    try {
      await onEnviar(limpio)
      setTexto('')
      area.current?.focus()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  if (deshabilitado) {
    return <div className="border-t border-marca-100 bg-white px-6 py-4 text-center text-sm text-slate-500">{motivo}</div>
  }

  return (
    <form onSubmit={enviar} className="border-t border-marca-100 bg-white px-4 py-3 sm:px-6">
      {error && <p role="alert" className="mb-2 text-sm text-red-700">{error}</p>}
      <div className="flex items-end gap-3">
        <label className="sr-only" htmlFor="redactar">{placeholder}</label>
        <textarea
          id="redactar"
          ref={area}
          rows={1}
          value={texto}
          maxLength={maximo}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) enviar(e)
          }}
          placeholder={placeholder}
          className="h-11 min-h-[44px] flex-1 resize-none truncate placeholder:truncate rounded-2xl border-0 bg-marca-50/60 px-4 py-3 text-sm text-marca-900 ring-1 ring-marca-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-marca-500"
        />
        <Boton type="submit" cargando={enviando} disabled={!texto.trim()} className="h-11 rounded-2xl" aria-label={textoBoton}>
          {!enviando && <Icono nombre="enviar" className="h-4 w-4" />}
          <span className="hidden sm:inline">{textoBoton}</span>
        </Boton>
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-slate-400">
        <span>Enter para enviar · Shift + Enter para un salto de línea</span>
        {texto.length > maximo * 0.8 && <span>{texto.length} / {maximo}</span>}
      </div>
    </form>
  )
}

// Estrellas de 1 a 5. Sin onElegir, solo muestran la calificacion.
export function Estrellas({ valor = 0, onElegir, tamano = 'h-7 w-7' }) {
  const [encima, setEncima] = useState(0)
  const mostrar = encima || valor
  const etiquetas = ['Muy mala', 'Mala', 'Regular', 'Buena', 'Excelente']
  return (
    <div className="flex items-center gap-1" role={onElegir ? 'radiogroup' : 'img'}
         aria-label={onElegir ? 'Califica la atención' : `${valor} de 5 estrellas`}>
      {[1, 2, 3, 4, 5].map((n) => {
        const llena = n <= mostrar
        const estrella = <Icono nombre="estrella" className={`${tamano} ${llena ? 'fill-current text-oro' : 'text-marca-200'}`} />
        if (!onElegir) return <span key={n}>{estrella}</span>
        return (
          <button key={n} type="button" role="radio" aria-checked={valor === n} aria-label={`${n}: ${etiquetas[n - 1]}`}
                  onMouseEnter={() => setEncima(n)} onMouseLeave={() => setEncima(0)} onClick={() => onElegir(n)}
                  className="rounded-md transition-transform hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-500">
            {estrella}
          </button>
        )
      })}
      {onElegir && mostrar > 0 && <span className="ml-2 text-sm text-marca-600">{etiquetas[mostrar - 1]}</span>}
    </div>
  )
}

// Textos comunes
export const TEMAS = {
  cuentas: 'Mis cuentas',
  transferencias: 'Transferencias',
  retiros: 'Retiros sin tarjeta',
  seguridad: 'Seguridad',
  otro: 'Otro tema',
}

export const ESTADOS_TIQUETE = {
  nuevo: { texto: 'Esperando asesor', color: 'bg-oro-claro/60 text-marca-900' },
  en_atencion: { texto: 'En atención', color: 'bg-marca-100 text-marca-700' },
  cerrado: { texto: 'Cerrado', color: 'bg-slate-100 text-slate-600' },
}

// Lista lateral de conversaciones
export function ListaConversaciones({ items, seleccionada, onElegir, titulo, subtitulo, vacio }) {
  if (!items) return <div className="flex justify-center py-10 text-marca-500"><Girando /></div>
  if (items.length === 0) return vacio
  return (
    <ul className="divide-y divide-marca-100">
      {items.map((it) => {
        const activa = it.id === seleccionada
        return (
          <li key={it.id}>
            <button onClick={() => onElegir(it)} aria-current={activa ? 'true' : undefined}
                    className={`flex w-full gap-3 px-4 py-3.5 text-left transition-colors ${activa ? 'bg-marca-50' : 'hover:bg-marca-50/50'}`}>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={`truncate text-sm ${it.no_leidos ? 'font-bold text-marca-900' : 'font-semibold text-marca-800'}`}>
                    {titulo(it)}
                  </span>
                  {it.no_leidos > 0 && (
                    <span className="grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-oro px-1.5 text-[11px] font-bold text-marca-900"
                          aria-label={`${it.no_leidos} sin leer`}>
                      {it.no_leidos}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 truncate text-xs text-slate-500">{subtitulo(it)}</div>
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
