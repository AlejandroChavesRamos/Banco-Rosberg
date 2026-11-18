// =====================================================================
// Asistente Rosberg (solo admin): el contestador automatico del chat.
//   - Resumen: cuanto responde, cuanto no entiende y si sus respuestas sirven.
//   - Activacion automatica y "Probar" (como lee un texto y que responderia).
//   - Lo que no entendio: con un clic se convierte en palabras clave.
//   - Respuestas: texto, palabras clave, temas relacionados (botones) y datos
//     del cliente que puede mostrar.
//   - Sinonimos: palabras que significan lo mismo.
// =====================================================================
import { useEffect, useState } from 'react'
import { api } from '../api'
import Icono from '../componentes/Icono'
import { Aviso, Boton, Campo, Cargando, Encabezado, EstadoVacio, Insignia, Selector, Tarjeta } from '../componentes/ui'
import { fechaHora } from '../formato'

const VACIA = { titulo: '', pregunta: '', respuesta: '', palabras: '', prioridad: 5, accion: '', relacionadas: [] }

const ACCIONES = {
  '': 'Ninguno (solo el texto)',
  envios: 'Sus envíos y lo que recibió',
  cuentas: 'El estado de sus cuentas',
  saldo: 'Su saldo',
  codigos_retiro: 'Sus códigos de retiro',
  llaves: 'Sus llaves',
  seguridad: 'Su seguridad (2FA y avisos)',
}

export default function Asistente() {
  const [respuestas, setRespuestas] = useState(null)
  const [config, setConfig] = useState({})
  const [resumen, setResumen] = useState(null)
  const [editando, setEditando] = useState(null) // null | 'nueva' | id
  const [aviso, setAviso] = useState(null)

  function cargar() {
    api.get('/atencion/respuestas').then(setRespuestas).catch((e) => setAviso({ tipo: 'error', texto: e.message }))
    api.get('/atencion/asistente/resumen').then(setResumen).catch(() => {})
    api.get('/admin/reglas').then((d) => {
      setConfig(Object.fromEntries(d.configuracion.map((c) => [c.clave, c.valor])))
    }).catch(() => {})
  }
  useEffect(cargar, [])
  const avisar = (texto, tipo = 'exito') => { setAviso({ tipo, texto }); cargar() }

  return (
    <div className="max-w-5xl space-y-6">
      <Encabezado titulo="Asistente Rosberg">
        Contesta las preguntas frecuentes del chat de ayuda, con los datos del cliente cuando hace falta.
        Si no entiende dos veces, o el cliente escribe “asesor”, pasa el caso a una persona.
      </Encabezado>
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      {resumen && <Resumen r={resumen} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <Activacion config={config} onCambio={avisar} />
        <Probar />
      </div>

      {respuestas && <Pendientes respuestas={respuestas} onCambio={avisar} />}

      <Tarjeta className="p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-marca-100 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-marca-700">Respuestas que conoce</h2>
            <p className="text-sm text-slate-500">
              Entre las que coinciden gana la de mayor prioridad (+2 si es un tema relacionado con lo que se venía hablando).
            </p>
          </div>
          <Boton onClick={() => setEditando('nueva')}>
            <Icono nombre="mas" className="h-4 w-4" /> Nueva respuesta
          </Boton>
        </div>
        {editando === 'nueva' && (
          <Formulario inicial={VACIA} todas={respuestas ?? []} onCancelar={() => setEditando(null)}
                      onGuardado={() => { setEditando(null); avisar('Respuesta creada') }} />
        )}
        {!respuestas ? <Cargando texto="Cargando respuestas" /> : (
          <ul className="divide-y divide-marca-100">
            {respuestas.map((r) => (
              <li key={r.id} className={r.activa ? '' : 'bg-slate-50'}>
                {editando === r.id ? (
                  <Formulario inicial={{ ...r, pregunta: r.pregunta ?? '', accion: r.accion ?? '', palabras: r.palabras.join(', ') }}
                              id={r.id} todas={respuestas} onCancelar={() => setEditando(null)}
                              onGuardado={() => { setEditando(null); avisar('Respuesta actualizada') }} />
                ) : (
                  <Fila r={r} todas={respuestas} onEditar={() => setEditando(r.id)} onCambio={avisar}
                        onError={(texto) => setAviso({ tipo: 'error', texto })} />
                )}
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      <Sinonimos onCambio={avisar} />
    </div>
  )
}

function Resumen({ r }) {
  const total = r.respondio + r.no_entendio + r.derivo
  const votos = r.util_si + r.util_no
  const datos = [
    ['Preguntas (30 días)', total.toLocaleString('es-CO')],
    ['Las respondió', total ? `${Math.round((r.respondio / total) * 100)} %` : '—'],
    ['Le sirvieron al cliente', votos ? `${Math.round((r.util_si / votos) * 100)} %` : '—', votos ? `${votos} votos` : 'sin votos aún'],
    ['Por revisar', r.por_revisar, 'preguntas que no entendió'],
  ]
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {datos.map(([titulo, valor, nota]) => (
        <Tarjeta key={titulo}>
          <div className="text-sm text-slate-500">{titulo}</div>
          <div className="cifras mt-1 font-titulo text-2xl font-bold text-marca-800">{valor}</div>
          {nota && <div className="text-xs text-slate-400">{nota}</div>}
        </Tarjeta>
      ))}
    </div>
  )
}

function Activacion({ config, onCambio }) {
  const encendido = config.ASISTENTE_AUTOMATICO === '1'
  const [minutos, setMinutos] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function guardar(clave, valor, texto) {
    setGuardando(true)
    try {
      await api.patch(`/admin/configuracion/${clave}`, { valor })
      onCambio(texto)
      setMinutos('')
    } catch (e) {
      onCambio(e.message, 'error')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Tarjeta className="space-y-4">
      <h2 className="text-lg font-semibold text-marca-700">Activación automática</h2>
      <label className="flex cursor-pointer items-start justify-between gap-4">
        <span>
          <span className="block font-medium text-marca-900">Tomar los tiquetes que nadie atiende</span>
          <span className="block text-sm text-slate-500">
            Si un tiquete nuevo lleva {config.MINUTOS_ASISTENTE ?? 5} minutos sin asesor, el asistente saluda y responde.
            También puedes encenderlo a mano en un tiquete desde Atención al cliente.
          </span>
        </span>
        <button type="button" role="switch" aria-checked={encendido} disabled={guardando}
                onClick={() => guardar('ASISTENTE_AUTOMATICO', encendido ? '0' : '1',
                  encendido ? 'Activación automática apagada' : 'Activación automática encendida')}
                className={`relative mt-1 h-7 w-12 shrink-0 rounded-full transition-colors ${encendido ? 'bg-marca-600' : 'bg-slate-300'}`}>
          <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${encendido ? 'left-6' : 'left-1'}`} />
        </button>
      </label>
      <form className="flex items-end gap-3" onSubmit={(e) => {
        e.preventDefault()
        guardar('MINUTOS_ASISTENTE', String(minutos), `Ahora espera ${minutos} minutos`)
      }}>
        <div className="w-40">
          <Campo etiqueta="Minutos de espera" type="number" min="1" max="120" required
                 placeholder={config.MINUTOS_ASISTENTE ?? '5'} value={minutos} onChange={(e) => setMinutos(e.target.value)} />
        </div>
        <Boton variante="secundario" type="submit" disabled={!minutos} cargando={guardando}>Guardar</Boton>
      </form>
    </Tarjeta>
  )
}

function Probar() {
  const [texto, setTexto] = useState('')
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')

  async function probar(e) {
    e.preventDefault()
    setError('')
    try {
      setResultado(await api.get(`/atencion/respuestas/probar?texto=${encodeURIComponent(texto)}`))
    } catch (err) {
      setError(err.message)
    }
  }

  const etiqueta = {
    responde: ['Respondería', 'bg-marca-100 text-marca-700'],
    no_entiende: ['No entiende', 'bg-amber-100 text-amber-800'],
    derivar: ['Pasa a un asesor', 'bg-slate-100 text-slate-700'],
  }

  return (
    <Tarjeta className="space-y-4">
      <h2 className="text-lg font-semibold text-marca-700">Probar</h2>
      <form onSubmit={probar} className="flex items-end gap-3">
        <div className="flex-1">
          <Campo etiqueta="Escribe como lo haría un cliente (con errores, si quieres)" required maxLength={1000}
                 placeholder="Ej.: se me olvido la clave" value={texto} onChange={(e) => setTexto(e.target.value)} />
        </div>
        <Boton type="submit" variante="secundario">Probar</Boton>
      </form>
      <Aviso>{error}</Aviso>
      {resultado && (
        <div className="space-y-2 rounded-2xl bg-marca-50/60 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Insignia color={etiqueta[resultado.resultado][1]}>{etiqueta[resultado.resultado][0]}</Insignia>
            {resultado.titulo && <span className="font-medium text-marca-800">{resultado.titulo}</span>}
            {resultado.coincidencias?.length > 0 && (
              <span className="text-xs text-slate-500">por: {resultado.coincidencias.join(', ')}</span>
            )}
          </div>
          {resultado.como_lo_lee && (
            <div className="text-xs text-slate-500">Lo lee como: <code className="text-marca-700">{resultado.como_lo_lee}</code></div>
          )}
          <p className="whitespace-pre-line text-marca-900">{resultado.respuesta}</p>
          {resultado.accion && (
            <p className="text-xs text-marca-600">+ mostraría al cliente: {ACCIONES[resultado.accion].toLowerCase()}</p>
          )}
          {resultado.sugeridas?.length > 0 && (
            <p className="text-xs text-slate-500">Palabras que podrías enseñarle: {resultado.sugeridas.join(', ')}</p>
          )}
        </div>
      )}
    </Tarjeta>
  )
}

// Lo que no entendio: el admin elige a que respuesta corresponde y que palabras aprender
function Pendientes({ respuestas, onCambio }) {
  const [lista, setLista] = useState(null)
  const cargar = () => api.get('/atencion/asistente/pendientes').then(setLista).catch(() => setLista([]))
  useEffect(() => { cargar() }, [])

  return (
    <Tarjeta className="p-0">
      <div className="border-b border-marca-100 px-6 py-4">
        <h2 className="text-lg font-semibold text-marca-700">Lo que no entendió</h2>
        <p className="text-sm text-slate-500">
          Enséñale: elige la respuesta correcta y las palabras que debió reconocer. La próxima vez lo entenderá.
        </p>
      </div>
      {!lista ? <Cargando /> : lista.length === 0 ? (
        <EstadoVacio icono="check" titulo="Nada pendiente">Cuando no entienda una pregunta, aparecerá aquí.</EstadoVacio>
      ) : (
        <ul className="divide-y divide-marca-100">
          {lista.map((c) => (
            <Pendiente key={c.id} c={c} respuestas={respuestas}
                       onListo={(texto) => { setLista((l) => l.filter((x) => x.id !== c.id)); onCambio(texto) }} />
          ))}
        </ul>
      )}
    </Tarjeta>
  )
}

function Pendiente({ c, respuestas, onListo }) {
  const [respuestaId, setRespuestaId] = useState('')
  const [palabras, setPalabras] = useState(c.sugeridas.join(', '))
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  async function ensenar(e) {
    e.preventDefault()
    setOcupado(true)
    setError('')
    try {
      const r = await api.post(`/atencion/asistente/pendientes/${c.id}/ensenar`, {
        respuesta_id: Number(respuestaId),
        palabras: palabras.split(',').map((p) => p.trim()).filter(Boolean),
      })
      onListo(`Aprendió: ${r.agregadas.join(', ')}`)
    } catch (err) {
      setError(err.message)
      setOcupado(false)
    }
  }

  async function descartar() {
    setOcupado(true)
    try {
      await api.post(`/atencion/asistente/pendientes/${c.id}/descartar`)
      onListo('Pregunta descartada')
    } catch (err) {
      setError(err.message)
      setOcupado(false)
    }
  }

  return (
    <li className="space-y-3 px-6 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium text-marca-900">“{c.texto}”</p>
        <span className="text-xs text-slate-400">
          {c.resultado === 'derivo' ? 'pasó a un asesor' : 'no entendió'} · {fechaHora(c.creada_en)}
        </span>
      </div>
      <form onSubmit={ensenar} className="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto_auto]">
        <Selector etiqueta="Debió responder" value={respuestaId} onChange={(e) => setRespuestaId(e.target.value)}
                  opciones={[{ valor: '', texto: 'Elegir respuesta…' },
                    ...respuestas.filter((r) => r.activa).map((r) => ({ valor: String(r.id), texto: r.titulo }))]} />
        <Campo etiqueta="Palabras a aprender (separadas por comas)" value={palabras} onChange={(e) => setPalabras(e.target.value)} />
        <Boton type="submit" disabled={!respuestaId || !palabras.trim()} cargando={ocupado}>Enseñar</Boton>
        <Boton type="button" variante="secundario" onClick={descartar} disabled={ocupado}>Descartar</Boton>
      </form>
      <Aviso>{error}</Aviso>
    </li>
  )
}

function Fila({ r, todas, onEditar, onCambio, onError }) {
  async function alternar() {
    try {
      await api.patch(`/atencion/respuestas/${r.id}`, { activa: !r.activa })
      onCambio(r.activa ? `“${r.titulo}” desactivada` : `“${r.titulo}” activada`)
    } catch (e) {
      onError(e.message)
    }
  }
  const votos = r.util_si + r.util_no
  const nombres = Object.fromEntries(todas.map((x) => [x.id, x.titulo]))
  return (
    <div className="flex flex-wrap items-start gap-4 px-6 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-semibold ${r.activa ? 'text-marca-800' : 'text-slate-400 line-through'}`}>{r.titulo}</span>
          {r.accion && <Insignia color="bg-oro-claro/60 text-marca-900">+ datos: {r.accion.replace('_', ' ')}</Insignia>}
          <span className="text-xs text-slate-500">
            prioridad {r.prioridad} · usada {r.usos} {r.usos === 1 ? 'vez' : 'veces'}
            {votos > 0 && ` · le sirvió al ${Math.round((r.util_si / votos) * 100)} % (${votos})`}
          </span>
        </div>
        {r.pregunta && <p className="mt-0.5 text-xs text-marca-600">Botón: “{r.pregunta}”</p>}
        <p className="mt-1 line-clamp-2 text-sm text-slate-600">{r.respuesta}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {r.palabras.map((p) => (
            <span key={p} className="rounded-full bg-marca-50 px-2 py-0.5 text-xs text-marca-700 ring-1 ring-marca-100">{p}</span>
          ))}
        </div>
        {r.relacionadas.length > 0 && (
          <p className="mt-2 text-xs text-slate-500">Relacionadas: {r.relacionadas.map((id) => nombres[id]).filter(Boolean).join(' · ')}</p>
        )}
      </div>
      <div className="flex gap-2">
        <Boton variante="secundario" className="py-2" onClick={onEditar}>Editar</Boton>
        <Boton variante="secundario" className="py-2" onClick={alternar}>{r.activa ? 'Desactivar' : 'Activar'}</Boton>
      </div>
    </div>
  )
}

function Formulario({ inicial, id, todas, onGuardado, onCancelar }) {
  const [datos, setDatos] = useState(inicial)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const cambiar = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value })

  function alternarRelacionada(rid) {
    const ya = datos.relacionadas.includes(rid)
    setDatos({ ...datos, relacionadas: ya ? datos.relacionadas.filter((x) => x !== rid) : [...datos.relacionadas, rid] })
  }

  async function guardar(e) {
    e.preventDefault()
    setError('')
    setGuardando(true)
    const cuerpo = {
      titulo: datos.titulo.trim(),
      pregunta: datos.pregunta.trim(),
      respuesta: datos.respuesta.trim(),
      prioridad: Number(datos.prioridad),
      // "llave, registrar mi celular" -> ["llave", "registrar mi celular"]
      palabras: datos.palabras.split(',').map((p) => p.trim()).filter(Boolean),
      relacionadas: datos.relacionadas,
    }
    if (id) cuerpo.accion = datos.accion || 'ninguna'
    else {
      if (datos.accion) cuerpo.accion = datos.accion
      if (!cuerpo.pregunta) delete cuerpo.pregunta
    }
    try {
      if (id) await api.patch(`/atencion/respuestas/${id}`, cuerpo)
      else await api.post('/atencion/respuestas', cuerpo)
      onGuardado()
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  const otras = todas.filter((r) => r.id !== id && r.activa && r.pregunta)

  return (
    <form onSubmit={guardar} className="space-y-4 border-b border-marca-100 bg-marca-50/40 px-6 py-5">
      <div className="grid gap-4 md:grid-cols-[1fr_1fr_140px]">
        <Campo etiqueta="Título (solo lo ve el admin)" required minLength={3} maxLength={80}
               value={datos.titulo} onChange={cambiar('titulo')} />
        <Campo etiqueta="Pregunta para los botones (opcional)" maxLength={120} placeholder="¿Cómo retiro sin tarjeta?"
               value={datos.pregunta} onChange={cambiar('pregunta')} />
        <Campo etiqueta="Prioridad (1 a 10)" type="number" min="1" max="10" required
               value={datos.prioridad} onChange={cambiar('prioridad')} />
      </div>
      <Campo etiqueta="Palabras clave, separadas por comas" required placeholder="llave, registrar mi celular, mis llaves"
             ayuda="No importan tildes, mayúsculas ni pequeños errores de escritura. Una frase corta pesa más que una palabra suelta."
             value={datos.palabras} onChange={cambiar('palabras')} />
      <label className="block">
        <span className="mb-1 block text-sm font-medium text-marca-800">Respuesta que verá el cliente</span>
        <textarea required minLength={5} maxLength={1000} rows={4} value={datos.respuesta} onChange={cambiar('respuesta')}
                  className="w-full resize-y rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm text-marca-900 ring-1 ring-marca-200 focus:outline-none focus:ring-2 focus:ring-marca-500" />
        <span className="mt-1 block text-xs text-slate-500">
          Puedes usar valores de la configuración: {'{RETIRO_MAXIMO}'}, {'{VIGENCIA_CODIGO_RETIRO}'}, {'{MONTO_2FA}'},
          {' {MAX_INTENTOS_LOGIN}'}, {'{MINUTOS_BLOQUEO_LOGIN}'}, {'{MAX_CUENTAS_CLIENTE}'}.
        </span>
      </label>
      <Selector etiqueta="Además, mostrar al cliente" value={datos.accion} onChange={cambiar('accion')}
                opciones={Object.entries(ACCIONES).map(([valor, texto]) => ({ valor, texto }))} />
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-marca-800">Temas relacionados (aparecen como botones después de esta respuesta)</legend>
        <div className="flex flex-wrap gap-2">
          {otras.map((r) => {
            const marcada = datos.relacionadas.includes(r.id)
            return (
              <button key={r.id} type="button" onClick={() => alternarRelacionada(r.id)} aria-pressed={marcada}
                      className={`rounded-full px-3 py-1 text-xs font-medium ring-1 transition-colors ${
                        marcada ? 'bg-marca-700 text-white ring-marca-700' : 'bg-white text-marca-700 ring-marca-200 hover:bg-marca-50'
                      }`}>
                {r.titulo}
              </button>
            )
          })}
        </div>
      </fieldset>
      <Aviso>{error}</Aviso>
      <div className="flex gap-3">
        <Boton type="submit" cargando={guardando}>Guardar</Boton>
        <Boton type="button" variante="secundario" onClick={onCancelar}>Cancelar</Boton>
      </div>
    </form>
  )
}

function Sinonimos({ onCambio }) {
  const [lista, setLista] = useState(null)
  const [palabra, setPalabra] = useState('')
  const [equivale, setEquivale] = useState('')
  const [error, setError] = useState('')
  const cargar = () => api.get('/atencion/asistente/sinonimos').then(setLista).catch(() => setLista([]))
  useEffect(() => { cargar() }, [])

  async function agregar(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/atencion/asistente/sinonimos', { palabra, equivale })
      setPalabra('')
      setEquivale('')
      cargar()
      onCambio('Sinónimo agregado')
    } catch (err) {
      setError(err.message)
    }
  }

  async function quitar(p) {
    try {
      await api.delete(`/atencion/asistente/sinonimos/${encodeURIComponent(p)}`)
      cargar()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Tarjeta className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-marca-700">Sinónimos</h2>
        <p className="text-sm text-slate-500">Antes de comparar, cada palabra se cambia por su equivalente: “clave” se lee como “contrasena”.</p>
      </div>
      <form onSubmit={agregar} className="flex flex-wrap items-end gap-3">
        <div className="w-44"><Campo etiqueta="Cuando escriban" required value={palabra} onChange={(e) => setPalabra(e.target.value)} placeholder="lucas" /></div>
        <div className="w-44"><Campo etiqueta="Entender" required value={equivale} onChange={(e) => setEquivale(e.target.value)} placeholder="dinero" /></div>
        <Boton type="submit" variante="secundario">Agregar</Boton>
      </form>
      <Aviso>{error}</Aviso>
      {!lista ? <Cargando /> : (
        <div className="flex flex-wrap gap-2">
          {lista.map((s) => (
            <span key={s.palabra} className="flex items-center gap-1.5 rounded-full bg-marca-50 py-1 pl-3 pr-1.5 text-xs text-marca-800 ring-1 ring-marca-100">
              {s.palabra} → <strong>{s.equivale}</strong>
              <button type="button" onClick={() => quitar(s.palabra)} aria-label={`Quitar ${s.palabra}`}
                      className="grid h-5 w-5 place-items-center rounded-full text-marca-500 hover:bg-white hover:text-red-600">
                <Icono nombre="cerrar" className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </Tarjeta>
  )
}
