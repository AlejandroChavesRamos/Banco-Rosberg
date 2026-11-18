// =====================================================================
// Atencion al cliente: los empleados responden las conversaciones de ayuda.
//   Pestanas: Nuevos (nadie los ha tomado) · Mis tiquetes · En atencion · Cerrados
//   El primer empleado que pulsa "Atender" queda a cargo; solo el escribe.
//   El admin puede reasignar un tiquete a otro empleado.
// =====================================================================
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ESTADOS_TIQUETE, Estrellas, ListaConversaciones, Mensajes, Redactar, TEMAS, useConversacion } from '../componentes/Chat'
import Icono from '../componentes/Icono'
import { usePeriodico } from '../componentes/usePeriodico'
import { Aviso, Boton, Encabezado, EstadoVacio, Insignia } from '../componentes/ui'
import { fechaHora } from '../formato'
import { useSesion } from '../sesion'

const VISTAS = [
  ['nuevos', 'Nuevos'],
  ['mios', 'Mis tiquetes'],
  ['en_atencion', 'En atención'],
  ['cerrados', 'Cerrados'],
]

const ROL = { cajero: 'Cajero', analista: 'Analista', admin: 'Administrador' }

export default function Atencion() {
  const [vista, setVista] = useState('nuevos')
  const [lista, setLista] = useState(null)
  const [elegido, setElegido] = useState(null)
  const [resumen, setResumen] = useState({ nuevos: 0, mios_no_leidos: 0 })

  function cargar() {
    api.get(`/atencion/tiquetes?vista=${vista}`).then(setLista).catch(() => {})
    api.get('/atencion/resumen').then(setResumen).catch(() => {})
  }
  usePeriodico(cargar, 5000)
  useEffect(() => { setLista(null); cargar() }, [vista])

  const contador = { nuevos: resumen.nuevos, mios: resumen.mios_no_leidos }

  return (
    <div className="space-y-6">
      <Encabezado titulo="Atención al cliente">
        Conversaciones de ayuda de los clientes. Toma una nueva con “Atender” y respóndela hasta cerrarla.
      </Encabezado>

      <div className="grid h-[calc(100vh-13rem)] min-h-[540px] overflow-hidden rounded-3xl bg-white shadow-sm shadow-marca-900/5 ring-1 ring-marca-100 grid-cols-[300px_1fr] lg:grid-cols-[340px_1fr]">
        <aside className="flex min-h-0 flex-col border-r border-marca-100">
          <div className="flex gap-1 overflow-x-auto border-b border-marca-100 p-2" role="tablist">
            {VISTAS.map(([valor, texto]) => (
              <button key={valor} role="tab" aria-selected={vista === valor} onClick={() => setVista(valor)}
                      className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                        vista === valor ? 'bg-marca-700 text-white' : 'text-marca-700 hover:bg-marca-50'
                      }`}>
                {texto}
                {contador[valor] > 0 && (
                  <span className="grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-oro px-1 text-[11px] font-bold text-marca-900">
                    {contador[valor]}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ListaConversaciones
              items={lista}
              seleccionada={elegido}
              onElegir={(t) => setElegido(t.id)}
              titulo={(t) => `${t.cliente.nombre} · ${t.asunto}`}
              subtitulo={(t) => `${TEMAS[t.tema]} · ${t.asesor ? t.asesor.nombre.split(' ')[0] : 'sin asesor'} · ${fechaHora(t.actualizado_en)}`}
              vacio={
                <EstadoVacio icono="chat" titulo={vista === 'nuevos' ? 'No hay clientes esperando' : 'Nada por aquí'}>
                  {vista === 'nuevos' ? 'Cuando un cliente pida ayuda, aparecerá en esta lista.' : 'No hay tiquetes en esta pestaña.'}
                </EstadoVacio>
              }
            />
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col">
          {elegido ? (
            <Tiquete key={elegido} id={elegido} onCambio={cargar} />
          ) : (
            <div className="grid flex-1 place-items-center">
              <EstadoVacio icono="soporte" titulo="Elige una conversación">
                Los tiquetes nuevos se atienden por orden de llegada: el que más lleva esperando está arriba.
              </EstadoVacio>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Tiquete({ id, onCambio }) {
  const { usuario } = useSesion()
  const { tiquete, setTiquete, mensajes, error, actualizar } = useConversacion(`/atencion/tiquetes/${id}`)
  const [accionError, setAccionError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  async function accion(ruta, cuerpo) {
    setAccionError('')
    setOcupado(true)
    try {
      setTiquete(await api.post(`/atencion/tiquetes/${id}/${ruta}`, cuerpo))
      onCambio()
    } catch (e) {
      setAccionError(e.message)
      actualizar()
    } finally {
      setOcupado(false)
    }
  }

  async function enviar(texto) {
    await api.post(`/atencion/tiquetes/${id}/mensajes`, { texto })
    await actualizar()
  }

  if (error && !tiquete) return <div className="p-6"><Aviso>{error}</Aviso></div>
  if (!tiquete) return <Mensajes mensajes={[]} cargando />

  const t = tiquete
  const estado = ESTADOS_TIQUETE[t.estado]
  const puedeCerrar = t.estado !== 'cerrado' && (t.a_mi_cargo || usuario.rol === 'admin')

  let motivo = ''
  if (t.estado === 'cerrado') motivo = `Tiquete cerrado el ${fechaHora(t.cerrado_en)}.`
  else if (t.estado === 'nuevo') motivo = 'Pulsa “Atender” para tomar este tiquete y responder.'
  else if (!t.a_mi_cargo) motivo = `Este tiquete lo atiende ${t.asesor.nombre}. Solo puedes leerlo.`

  return (
    <>
      <header className="space-y-3 border-b border-marca-100 px-6 py-4">
        <div className="flex flex-wrap items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-marca-100 text-marca-700">
            <Icono nombre="usuario" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-marca-900">{t.cliente.nombre}</div>
            <div className="truncate text-xs text-slate-500">{t.cliente.email} · desde {fechaHora(t.creado_en)}</div>
          </div>
          <Insignia color={estado.color}>{estado.texto}</Insignia>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="font-medium text-marca-800">{t.asunto}</span>
          <span className="text-slate-500">{TEMAS[t.tema]}</span>
          {t.asesor && <span className="text-slate-500">Asesor: {t.asesor.nombre} ({ROL[t.asesor.rol]})</span>}
          {t.calificacion && <Estrellas valor={t.calificacion} tamano="h-4 w-4" />}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {t.estado === 'nuevo' && (
            <Boton onClick={() => accion('atender')} cargando={ocupado}>
              <Icono nombre="soporte" className="h-4 w-4" />
              Atender
            </Boton>
          )}
          {puedeCerrar && (
            <Boton variante="secundario" onClick={() => accion('cerrar')} cargando={ocupado}>
              <Icono nombre="check" className="h-4 w-4" />
              Cerrar tiquete
            </Boton>
          )}
          {usuario.rol === 'admin' && t.estado !== 'cerrado' && (
            <Reasignar actual={t.asesor?.id} onElegir={(asesor_id) => accion('reasignar', { asesor_id })} />
          )}
        </div>
        <Aviso>{accionError}</Aviso>
      </header>

      <Mensajes mensajes={mensajes} />
      <Redactar onEnviar={enviar} deshabilitado={Boolean(motivo)} motivo={motivo}
                placeholder={`Responder a ${t.cliente.nombre.split(' ')[0]}`} textoBoton="Responder" />
    </>
  )
}

function Reasignar({ actual, onElegir }) {
  const [asesores, setAsesores] = useState(null)
  useEffect(() => { api.get('/atencion/asesores').then(setAsesores).catch(() => setAsesores([])) }, [])
  if (!asesores) return null
  return (
    <label className="flex items-center gap-2 text-sm text-marca-700">
      <span>Reasignar a</span>
      <select value="" onChange={(e) => e.target.value && onElegir(Number(e.target.value))}
              className="rounded-xl border-0 bg-white px-3 py-2 text-sm ring-1 ring-marca-200 focus:outline-none focus:ring-2 focus:ring-marca-500">
        <option value="">Elegir empleado…</option>
        {asesores.filter((a) => a.id !== actual).map((a) => (
          <option key={a.id} value={a.id}>{a.nombre} ({ROL[a.rol]})</option>
        ))}
      </select>
    </label>
  )
}
