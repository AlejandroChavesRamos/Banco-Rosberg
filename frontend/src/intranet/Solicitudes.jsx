// =====================================================================
// Bandeja de solicitudes: los correos que dejan los visitantes en la pagina
// publica (pedir tarjeta, contacto, trabaja con nosotros).
// Cada solicitud se abre como una conversacion: lo que escribio el visitante
// a la izquierda y las respuestas del banco a la derecha. Cada respuesta se
// ENVIA al correo del visitante (en desarrollo llega a Mailpit:
// http://localhost:8025). Si el correo falla, se puede reintentar.
// =====================================================================
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ListaConversaciones, Mensajes, Redactar } from '../componentes/Chat'
import Icono from '../componentes/Icono'
import { usePeriodico } from '../componentes/usePeriodico'
import { Aviso, Boton, Encabezado, EstadoVacio, Insignia } from '../componentes/ui'
import { fechaHora } from '../formato'

const TIPOS = {
  tarjeta: { texto: 'Tarjeta física', icono: 'ventanilla', color: 'bg-oro-claro/60 text-marca-900' },
  contacto: { texto: 'Contacto', icono: 'arroba', color: 'bg-marca-100 text-marca-700' },
  empleo: { texto: 'Trabaja con nosotros', icono: 'empleados', color: 'bg-slate-100 text-slate-700' },
}

const SIN_MENSAJE = {
  tarjeta: 'Quiere recibir la tarjeta débito física.',
  contacto: 'Pide que el banco le escriba.',
  empleo: 'Dejó su correo para trabajar en el banco.',
}

export default function Solicitudes() {
  const [verAtendidas, setVerAtendidas] = useState(false)
  const [lista, setLista] = useState(null)
  const [elegida, setElegida] = useState(null)
  const [error, setError] = useState('')

  function cargar() {
    api.get(`/publico/solicitudes?atendidas=${verAtendidas}`).then(setLista).catch((e) => setError(e.message))
  }
  usePeriodico(cargar, 10000)
  useEffect(() => { setLista(null); cargar() }, [verAtendidas])

  return (
    <div className="space-y-6">
      <Encabezado
        titulo="Solicitudes"
        acciones={
          <div className="flex rounded-full bg-white p-1 ring-1 ring-marca-200" role="tablist">
            {[[false, 'Pendientes'], [true, 'Atendidas']].map(([valor, texto]) => (
              <button key={texto} role="tab" aria-selected={verAtendidas === valor} onClick={() => setVerAtendidas(valor)}
                      className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                        verAtendidas === valor ? 'bg-marca-700 text-white' : 'text-marca-700 hover:bg-marca-50'
                      }`}>
                {texto}
              </button>
            ))}
          </div>
        }
      >
        Lo que dejaron los visitantes en la página del banco. Tu respuesta les llega por correo.
      </Encabezado>
      <Aviso>{error}</Aviso>

      <div className="grid h-[calc(100vh-13rem)] min-h-[540px] grid-cols-[300px_1fr] overflow-hidden rounded-3xl bg-white shadow-sm shadow-marca-900/5 ring-1 ring-marca-100 lg:grid-cols-[340px_1fr]">
        <aside className="min-h-0 overflow-y-auto border-r border-marca-100">
          <ListaConversaciones
            items={lista}
            seleccionada={elegida}
            onElegir={(s) => setElegida(s.id)}
            titulo={(s) => s.email}
            subtitulo={(s) => `${TIPOS[s.tipo].texto} · ${s.respuestas ? `${s.respuestas} respuesta${s.respuestas > 1 ? 's' : ''}` : 'sin responder'}${s.sin_enviar ? ' · ⚠ correo sin enviar' : ''}`}
            vacio={
              <EstadoVacio icono="buzon" titulo={verAtendidas ? 'Aún no hay solicitudes atendidas' : 'No hay solicitudes pendientes'}>
                {verAtendidas ? 'Las que respondas o marques como atendidas quedarán aquí.'
                  : 'Cuando alguien pida la tarjeta, escriba por contacto o quiera unirse al equipo, aparecerá aquí.'}
              </EstadoVacio>
            }
          />
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col">
          {elegida ? (
            <Hilo key={elegida} id={elegida} onCambio={cargar} />
          ) : (
            <div className="grid flex-1 place-items-center">
              <EstadoVacio icono="arroba" titulo="Elige una solicitud">
                Al responder, el visitante recibe tu mensaje en su correo y la solicitud pasa a “Atendidas”.
              </EstadoVacio>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Hilo({ id, onCambio }) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState(null)

  const cargar = () => api.get(`/publico/solicitudes/${id}`).then(setDatos).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [id])

  async function responder(texto) {
    const r = await api.post(`/publico/solicitudes/${id}/respuestas`, { texto })
    setAviso(r.estado_envio === 'enviado' ? { tipo: 'exito', texto: r.mensaje } : { tipo: 'advertencia', texto: r.mensaje })
    await cargar()
    onCambio()
  }

  async function reintentar(respuestaId) {
    setAviso(null)
    try {
      const r = await api.post(`/publico/solicitudes/${id}/respuestas/${respuestaId}/reintentar`)
      setAviso(r.estado_envio === 'enviado' ? { tipo: 'exito', texto: 'Correo enviado' }
        : { tipo: 'advertencia', texto: 'El servidor de correo sigue sin responder' })
      await cargar()
      onCambio()
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.message })
    }
  }

  async function marcar(atendida) {
    try {
      await api.patch(`/publico/solicitudes/${id}`, { atendida })
      await cargar()
      onCambio()
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.message })
    }
  }

  if (error) return <div className="p-6"><Aviso>{error}</Aviso></div>
  if (!datos) return <Mensajes mensajes={[]} cargando />

  const s = datos.solicitud
  const tipo = TIPOS[s.tipo]
  // La solicitud original es la primera "burbuja"; las respuestas del banco, las demas
  const burbujas = [
    { id: 'original', texto: s.mensaje || SIN_MENSAJE[s.tipo], creado_en: s.creada_en, mio: false, autor: s.email },
    ...datos.respuestas.map((r) => ({ ...r, id: r.id, mio: true, autor: r.autor })),
  ]

  return (
    <>
      <header className="flex flex-wrap items-center gap-3 border-b border-marca-100 px-6 py-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-marca-100 text-marca-700">
          <Icono nombre={tipo.icono} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-marca-900">{s.email}</div>
          <div className="text-xs text-slate-500">Visitante (sin cuenta) · {fechaHora(s.creada_en)}</div>
        </div>
        <Insignia color={tipo.color}>{tipo.texto}</Insignia>
        {s.atendida ? (
          <Boton variante="secundario" className="py-2" onClick={() => marcar(false)}>Volver a pendientes</Boton>
        ) : (
          <Boton variante="secundario" className="py-2" onClick={() => marcar(true)}>
            <Icono nombre="check" className="h-4 w-4" />
            Atendida sin responder
          </Boton>
        )}
      </header>

      <Mensajes
        mensajes={burbujas}
        pie={(m) => m.mio && <EstadoEnvio r={m} onReintentar={() => reintentar(m.id)} />}
      />

      {aviso && <div className="px-6 pt-3"><Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso></div>}
      <Redactar onEnviar={responder} maximo={2000} textoBoton="Enviar por correo"
                placeholder="Escribe tu respuesta: le llegará por correo" />
    </>
  )
}

function EstadoEnvio({ r, onReintentar }) {
  if (r.estado_envio === 'enviado') {
    return <div className="mt-1 text-right text-[11px] text-marca-600">✓ Enviado al correo · {r.autor}</div>
  }
  return (
    <div className="mt-1 flex items-center justify-end gap-2 text-[11px] text-red-700">
      <span>⚠ {r.estado_envio === 'fallido' ? 'No se pudo enviar el correo' : 'Enviando…'}</span>
      {r.estado_envio === 'fallido' && (
        <button onClick={onReintentar} className="font-semibold underline hover:text-red-900">Reintentar</button>
      )}
    </div>
  )
}
