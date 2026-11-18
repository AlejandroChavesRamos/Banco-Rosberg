// Mis llaves: registrar el celular o el correo para recibir transferencias
import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAviso } from '../componentes/Avisos'
import Icono from '../componentes/Icono'
import { Aviso, Boton, Selector, Tarjeta, EstadoVacio } from '../componentes/ui'
import { enmascarar, fechaHora } from '../formato'

export default function Llaves() {
  const [llaves, setLlaves] = useState([])
  const [cuentas, setCuentas] = useState([])
  const [tipo, setTipo] = useState('celular')
  const [cuenta, setCuenta] = useState('')
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' })
  const avisar = useAviso()
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    cargar()
    api.get('/cuentas').then((lista) => {
      const activas = lista.filter((c) => c.estado === 'activa')
      setCuentas(activas)
      if (activas.length) setCuenta(activas[0].numero)
    })
  }, [])

  function cargar() {
    api.get('/llaves').then(setLlaves).catch((e) => setMensaje({ tipo: 'error', texto: e.message }))
  }

  async function registrar(evento) {
    evento.preventDefault()
    setCargando(true)
    setMensaje({ tipo: '', texto: '' })
    try {
      const r = await api.post('/llaves', { tipo, cuenta })
      avisar(`Llave registrada: ya te pueden enviar dinero a ${r.valor}`)
      cargar()
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e.message })
    } finally {
      setCargando(false)
    }
  }

  async function desactivar(id) {
    if (!confirm('¿Desactivar esta llave? Ya no podrán enviarte dinero con ella.')) return
    try {
      await api.delete(`/llaves/${id}`)
      avisar('Llave desactivada')
      cargar()
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e.message })
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Mis llaves</h1>
        <p className="text-sm text-slate-500">Recibe dinero sin compartir tu número de cuenta.</p>
      </div>

      {/* Dos columnas en computador: llaves a la izquierda, registrar a la derecha */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
      <Tarjeta className="p-0">
        {llaves.length === 0 ? (
          <EstadoVacio icono="llave" titulo="Aún no tienes llaves">
            Registra tu celular o tu correo para que te envíen dinero sin pedirte el número de cuenta.
          </EstadoVacio>
        ) : (
          <ul className="divide-y divide-slate-100">
            {llaves.map((l) => (
              <li key={l.id} className="flex items-center gap-3 px-5 py-4">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-marca-50 text-marca-700">
                  <Icono nombre={l.tipo === 'celular' ? 'telefono' : 'arroba'} className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{l.valor}</div>
                  <div className="text-xs text-slate-500">
                    Llega a {enmascarar(l.cuenta)} · desde {fechaHora(l.creada_en)}
                  </div>
                </div>
                <button onClick={() => desactivar(l.id)} className="text-xs font-medium text-red-600 hover:underline">
                  Desactivar
                </button>
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      <Tarjeta>
        <h2 className="mb-4 text-lg font-semibold text-marca-700">Registrar una llave</h2>
        <form onSubmit={registrar} className="space-y-4">
          <Selector
            etiqueta="Tipo de llave"
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            opciones={[
              { valor: 'celular', texto: 'Mi celular' },
              { valor: 'correo', texto: 'Mi correo' },
            ]}
          />
          <Selector
            etiqueta="Cuenta donde recibir"
            value={cuenta}
            onChange={(e) => setCuenta(e.target.value)}
            opciones={cuentas.map((c) => ({ valor: c.numero, texto: `Ahorros ${enmascarar(c.numero)}` }))}
          />
          <p className="text-xs text-slate-500">
            Por seguridad, solo puedes registrar el celular y el correo que tienes inscritos en el banco.
          </p>
          <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>
          <Boton type="submit" cargando={cargando} className="w-full">Registrar llave</Boton>
        </form>
      </Tarjeta>
      </div>
    </div>
  )
}
