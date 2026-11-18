// =====================================================================
// Ayuda: el cliente conversa con un asesor del banco.
//   Izquierda: sus conversaciones (abiertas primero).
//   Derecha:   la conversacion elegida, o el formulario para abrir una nueva.
// Cada conversacion es un "tiquete": lo toma un empleado y se cierra cuando
// el caso se resuelve. Al cerrarse, el cliente califica la atencion.
// =====================================================================
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { ESTADOS_TIQUETE, Estrellas, ListaConversaciones, Mensajes, Redactar, TEMAS, useConversacion } from '../componentes/Chat'
import Icono from '../componentes/Icono'
import { usePeriodico } from '../componentes/usePeriodico'
import { Aviso, Boton, Campo, EstadoVacio, Insignia, Selector } from '../componentes/ui'
import { fechaHora } from '../formato'

export default function Ayuda() {
  const { id } = useParams() // /app/ayuda/:id  o  /app/ayuda/nueva
  const navegar = useNavigate()
  const [lista, setLista] = useState(null)

  const cargarLista = () => api.get('/ayuda/tiquetes').then(setLista).catch(() => {})
  usePeriodico(cargarLista, 8000)

  const nueva = id === 'nueva'
  const elegida = !nueva && id ? Number(id) : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Ayuda</h1>
        <p className="text-sm text-slate-500">Escríbele a un asesor de Banco Rosberg. Te respondemos por aquí mismo.</p>
      </div>

      <div className="grid h-[calc(100vh-15rem)] min-h-[520px] overflow-hidden rounded-3xl bg-white shadow-sm shadow-marca-900/5 ring-1 ring-marca-100 lg:grid-cols-[320px_1fr]">
        {/* Lista de conversaciones (en pantallas angostas se oculta si hay una abierta) */}
        <aside className={`flex min-h-0 flex-col border-marca-100 lg:border-r ${id ? 'hidden lg:flex' : 'flex'}`}>
          <div className="border-b border-marca-100 p-4">
            <Boton className="w-full" onClick={() => navegar('/app/ayuda/nueva')}>
              <Icono nombre="mas" className="h-4 w-4" />
              Nueva conversación
            </Boton>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ListaConversaciones
              items={lista}
              seleccionada={elegida}
              onElegir={(t) => navegar(`/app/ayuda/${t.id}`)}
              titulo={(t) => t.asunto}
              subtitulo={(t) => `${ESTADOS_TIQUETE[t.estado].texto} · ${t.ultimo_mensaje ?? ''}`}
              vacio={
                <EstadoVacio icono="chat" titulo="Aún no has escrito">
                  Si tienes una duda con tus cuentas, envíos o retiros, abre una conversación.
                </EstadoVacio>
              }
            />
          </div>
        </aside>

        <section className={`flex min-h-0 flex-col ${id ? 'flex' : 'hidden lg:flex'}`}>
          {nueva ? (
            <NuevaConversacion onCreada={(t) => { cargarLista(); navegar(`/app/ayuda/${t.id}`, { replace: true }) }}
                               onVolver={() => navegar('/app/ayuda')} />
          ) : elegida ? (
            <Conversacion id={elegida} onCambio={cargarLista} onVolver={() => navegar('/app/ayuda')} />
          ) : (
            <div className="grid flex-1 place-items-center">
              <EstadoVacio icono="soporte" titulo="¿En qué te ayudamos?"
                           accion={<Boton variante="secundario" onClick={() => navegar('/app/ayuda/nueva')}>Escribir a un asesor</Boton>}>
                Elige una conversación de la lista o abre una nueva. Un asesor te responderá en horario de atención.
              </EstadoVacio>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function NuevaConversacion({ onCreada, onVolver }) {
  const [tema, setTema] = useState('transferencias')
  const [asunto, setAsunto] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      onCreada(await api.post('/ayuda/tiquetes', { tema, asunto: asunto.trim(), mensaje: mensaje.trim() }))
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="overflow-y-auto p-6 sm:p-8">
      <button onClick={onVolver} className="mb-4 text-sm font-medium text-marca-600 hover:text-marca-800 lg:hidden">← Mis conversaciones</button>
      <h2 className="font-titulo text-2xl font-bold text-marca-700">Nueva conversación</h2>
      <p className="mt-1 text-sm text-slate-500">Cuéntanos qué pasó. Nunca te pediremos tu contraseña ni tus códigos.</p>
      <form onSubmit={enviar} className="mt-6 max-w-xl space-y-5">
        <Selector etiqueta="Tema" value={tema} onChange={(e) => setTema(e.target.value)}
                  opciones={Object.entries(TEMAS).map(([valor, texto]) => ({ valor, texto }))} />
        <Campo etiqueta="Asunto" required minLength={3} maxLength={120} placeholder="Ej.: No me llegó una transferencia"
               value={asunto} onChange={(e) => setAsunto(e.target.value)} />
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-marca-800">Mensaje</span>
          <textarea required maxLength={1000} rows={5} value={mensaje} onChange={(e) => setMensaje(e.target.value)}
                    placeholder="Describe tu caso: qué hiciste, cuándo y por cuánto dinero."
                    className="w-full resize-y rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm text-marca-900 ring-1 ring-marca-200 placeholder:text-slate-400 hover:ring-marca-300 focus:outline-none focus:ring-2 focus:ring-marca-500" />
          <span className="mt-1 block text-right text-xs text-slate-400">{mensaje.length} / 1000</span>
        </label>
        <Aviso>{error}</Aviso>
        <Boton type="submit" cargando={enviando}>Enviar al banco</Boton>
      </form>
    </div>
  )
}

function Conversacion({ id, onCambio, onVolver }) {
  const { tiquete, setTiquete, mensajes, error, actualizar } = useConversacion(`/ayuda/tiquetes/${id}`)
  const [cerrando, setCerrando] = useState(false)

  // Al leer, el contador de "sin leer" de la lista baja
  useEffect(() => { if (mensajes.length) onCambio() }, [mensajes.length])

  async function enviar(texto) {
    await api.post(`/ayuda/tiquetes/${id}/mensajes`, { texto })
    await actualizar()
    onCambio()
  }

  if (error && !tiquete) return <div className="p-6"><Aviso>{error}</Aviso></div>

  const estado = tiquete ? ESTADOS_TIQUETE[tiquete.estado] : null
  const cerrado = tiquete?.estado === 'cerrado'

  return (
    <>
      <header className="flex flex-wrap items-center gap-3 border-b border-marca-100 px-4 py-3 sm:px-6">
        <button onClick={onVolver} className="text-marca-600 lg:hidden" aria-label="Volver a mis conversaciones">←</button>
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-marca-700 text-white">
          <Icono nombre="soporte" className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-marca-900">{tiquete?.asunto ?? 'Cargando…'}</div>
          <div className="text-xs text-slate-500">
            {tiquete && (tiquete.asesor ? `Te atiende ${tiquete.asesor}` : 'Esperando a que un asesor tome tu caso')}
            {tiquete && ` · ${TEMAS[tiquete.tema]}`}
          </div>
        </div>
        {estado && <Insignia color={estado.color}>{estado.texto}</Insignia>}
        {tiquete && !cerrado && (
          <Boton variante="secundario" className="py-2" onClick={() => setCerrando(true)}>Finalizar</Boton>
        )}
      </header>

      <Mensajes mensajes={mensajes} cargando={!tiquete} />

      {cerrando && tiquete && !cerrado && (
        <CerrarConCalificacion id={id} onListo={(t) => { setTiquete(t); setCerrando(false); onCambio() }}
                               onCancelar={() => setCerrando(false)} />
      )}

      {cerrado ? (
        <PieCerrado tiquete={tiquete} onCalificado={(t) => { setTiquete(t); onCambio() }} />
      ) : (
        !cerrando && <Redactar onEnviar={enviar} placeholder="Escribe tu mensaje" deshabilitado={!tiquete} />
      )}
    </>
  )
}

function CerrarConCalificacion({ id, onListo, onCancelar }) {
  const [calificacion, setCalificacion] = useState(0)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function cerrar() {
    setEnviando(true)
    try {
      onListo(await api.post(`/ayuda/tiquetes/${id}/cerrar`, { calificacion: calificacion || null }))
    } catch (e) {
      setError(e.message)
      setEnviando(false)
    }
  }

  return (
    <div className="space-y-3 border-t border-marca-100 bg-white px-6 py-5">
      <div className="font-semibold text-marca-800">¿Se resolvió tu caso? Califica la atención</div>
      <Estrellas valor={calificacion} onElegir={setCalificacion} />
      <Aviso>{error}</Aviso>
      <div className="flex gap-3">
        <Boton onClick={cerrar} cargando={enviando}>Finalizar conversación</Boton>
        <Boton variante="secundario" onClick={onCancelar}>Seguir escribiendo</Boton>
      </div>
    </div>
  )
}

function PieCerrado({ tiquete, onCalificado }) {
  const [error, setError] = useState('')

  async function calificar(n) {
    try {
      onCalificado(await api.post(`/ayuda/tiquetes/${tiquete.id}/calificar`, { calificacion: n }))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-2 border-t border-marca-100 bg-white px-6 py-4 text-sm">
      <div className="text-slate-500">Conversación finalizada el {fechaHora(tiquete.cerrado_en)}. Si necesitas algo más, abre una nueva.</div>
      {tiquete.calificacion ? (
        <div className="flex items-center gap-2 text-marca-700">Tu calificación: <Estrellas valor={tiquete.calificacion} tamano="h-5 w-5" /></div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-medium text-marca-800">¿Cómo te atendimos?</span>
          <Estrellas onElegir={calificar} tamano="h-6 w-6" />
        </div>
      )}
      <Aviso>{error}</Aviso>
    </div>
  )
}
