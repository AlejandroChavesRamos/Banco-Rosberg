// Reglas antifraude: el admin ajusta pesos, umbrales y activa/desactiva reglas.
// El motor lee estos valores en cada operacion: el cambio aplica de inmediato.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Aviso, Boton, Insignia, Tarjeta } from '../componentes/ui'

export default function Reglas() {
  const [reglas, setReglas] = useState([])
  const [configuracion, setConfiguracion] = useState([])
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' })

  useEffect(() => {
    cargar()
  }, [])

  function cargar() {
    api.get('/admin/reglas').then((d) => {
      setReglas(d.reglas)
      setConfiguracion(d.configuracion)
    })
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Reglas antifraude</h1>
        <p className="text-sm text-slate-500">
          Cada regla que se cumple suma su peso al puntaje de la operación. Los cambios aplican de inmediato y quedan en la
          auditoría.
        </p>
      </div>
      <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>

      <div className="grid gap-4 md:grid-cols-2">
        {reglas.map((r) => (
          <FilaRegla key={r.codigo} regla={r} onGuardada={(texto) => { setMensaje({ tipo: 'exito', texto }); cargar() }}
                     onError={(texto) => setMensaje({ tipo: 'error', texto })} />
        ))}
      </div>

      <Interruptores configuracion={configuracion} onCambio={(texto, tipo = 'exito') => { setMensaje({ tipo, texto }); cargar() }} />

      <Tarjeta>
        <h2 className="mb-3 text-lg font-semibold text-marca-700">Umbrales de decisión</h2>
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          {configuracion.filter((c) => !c.clave.startsWith('2FA') && c.clave !== 'MONTO_2FA' && !c.clave.includes('ASISTENTE')).map((c) => (
            <div key={c.clave} className="flex justify-between gap-4 border-b border-slate-100 py-1.5">
              <span className="text-slate-500">{c.descripcion}</span>
              <span className="cifras font-semibold">{Number(c.valor).toLocaleString('es-CO')}</span>
            </div>
          ))}
        </div>
      </Tarjeta>
    </div>
  )
}

// Interruptores de verificacion en dos pasos (cada cambio queda en la auditoria)
const INTERRUPTORES = [
  ['2FA_EMPLEADOS', 'Obligatoria para empleados', 'Todos los empleados deberán vincular su app autenticadora y dar el código al entrar.'],
  ['2FA_CLIENTES', 'Permitir a clientes', 'Aparece en la App la opción de activar la verificación en dos pasos.'],
  ['2FA_TRANSFERENCIAS', 'Exigir en envíos grandes', 'Los clientes deben dar el código para transferir desde el monto indicado.'],
]

function Interruptores({ configuracion, onCambio }) {
  const valor = (clave) => configuracion.find((c) => c.clave === clave)?.valor
  const [monto, setMonto] = useState('')
  const [guardando, setGuardando] = useState(null)

  async function cambiar(clave, nuevo) {
    if (clave === '2FA_EMPLEADOS' && nuevo === '1' &&
        !confirm('Todos los empleados (incluido tú) deberán configurar Google Authenticator antes de seguir trabajando. ¿Continuar?')) return
    setGuardando(clave)
    try {
      await api.patch(`/admin/configuracion/${clave}`, { valor: nuevo })
      onCambio(`${clave} ${nuevo === '1' ? 'encendido' : nuevo === '0' ? 'apagado' : 'actualizado'}`)
    } catch (e) {
      onCambio(e.message, 'error')
    } finally {
      setGuardando(null)
    }
  }

  return (
    <Tarjeta className="space-y-4">
      <div>
        <h2 className="font-semibold">Verificación en dos pasos (2FA)</h2>
        <p className="text-sm text-slate-500">Código de Google Authenticator además de la contraseña.</p>
      </div>
      {INTERRUPTORES.map(([clave, titulo, ayuda]) => {
        const encendido = valor(clave) === '1'
        return (
          <div key={clave} className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3">
            <div>
              <div className="text-sm font-medium">{titulo}</div>
              <div className="text-xs text-slate-500">{ayuda}</div>
            </div>
            <button
              onClick={() => cambiar(clave, encendido ? '0' : '1')}
              disabled={guardando === clave}
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${encendido ? 'bg-marca-600' : 'bg-slate-300'}`}
              title={encendido ? 'Apagar' : 'Encender'}
            >
              <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${encendido ? 'left-[22px]' : 'left-0.5'}`} />
            </button>
          </div>
        )
      })}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Monto desde el que se exige en envíos (actual: ${Number(valor('MONTO_2FA') ?? 0).toLocaleString('es-CO')})</span>
          <input type="number" min="1000" step="1000" value={monto} onChange={(e) => setMonto(e.target.value)}
                 className="w-48 rounded-lg border-0 bg-white px-3 py-1.5 ring-1 ring-slate-200" />
        </label>
        <Boton variante="secundario" disabled={!monto} cargando={guardando === 'MONTO_2FA'}
               onClick={() => { cambiar('MONTO_2FA', String(Math.round(Number(monto)))); setMonto('') }}>
          Guardar monto
        </Boton>
      </div>
    </Tarjeta>
  )
}

function FilaRegla({ regla, onGuardada, onError }) {
  const [peso, setPeso] = useState(regla.peso)
  const [umbral, setUmbral] = useState(regla.umbral ?? '')
  const [activa, setActiva] = useState(Boolean(regla.activa))
  const [guardando, setGuardando] = useState(false)
  const cambio = peso !== regla.peso || String(umbral) !== String(regla.umbral ?? '') || activa !== Boolean(regla.activa)

  async function guardar() {
    setGuardando(true)
    try {
      const cuerpo = { peso: Number(peso), activa }
      if (umbral !== '') cuerpo.umbral = Number(umbral)
      await api.patch(`/admin/reglas/${regla.codigo}`, cuerpo)
      onGuardada(`Regla ${regla.codigo} actualizada`)
    } catch (e) {
      onError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Tarjeta className={`space-y-3 ${activa ? '' : 'opacity-60'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm font-semibold">{regla.codigo}</div>
          <div className="text-xs text-slate-500">{regla.descripcion}</div>
        </div>
        <Insignia color={regla.motor === 'neo4j' ? 'bg-marca-100 text-marca-700' : 'bg-oro-claro/60 text-marca-900'}>
          {regla.motor === 'neo4j' ? 'Neo4j' : 'MySQL'}
        </Insignia>
      </div>
      <label className="block text-sm">
        <div className="mb-1 flex justify-between"><span className="text-slate-500">Peso</span><span className="cifras font-semibold">+{peso}</span></div>
        <input type="range" min="0" max="100" value={peso} onChange={(e) => setPeso(Number(e.target.value))} className="w-full accent-marca-700" />
      </label>
      <div className="flex items-end gap-3">
        {regla.umbral !== null && (
          <label className="block flex-1 text-sm">
            <span className="mb-1 block text-slate-500">Umbral (N)</span>
            <input type="number" step="0.5" min="0" value={umbral} onChange={(e) => setUmbral(e.target.value)}
                   className="w-full rounded-lg border-0 bg-white px-3 py-1.5 ring-1 ring-slate-200" />
          </label>
        )}
        <label className="flex items-center gap-2 pb-1.5 text-sm">
          <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} className="accent-marca-700" />
          Activa
        </label>
        <Boton className="ml-auto" disabled={!cambio} cargando={guardando} onClick={guardar}>Guardar</Boton>
      </div>
    </Tarjeta>
  )
}
