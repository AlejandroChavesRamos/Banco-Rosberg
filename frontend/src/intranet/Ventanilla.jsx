// =====================================================================
// Ventanilla del cajero: buscar cliente, depositar, entregar retiros con
// codigo, crear clientes y abrir cuentas.
// =====================================================================
import { useState } from 'react'
import { api } from '../api'
import { Aviso, Boton, Campo, Insignia, Selector, Tarjeta } from '../componentes/ui'
import { cop } from '../formato'

const PESTANAS = [
  { id: 'buscar', texto: 'Buscar cliente' },
  { id: 'depositar', texto: 'Depositar' },
  { id: 'retiro', texto: 'Entregar retiro' },
  { id: 'nuevo', texto: 'Nuevo cliente' },
  { id: 'cuenta', texto: 'Abrir cuenta' },
]

export default function Ventanilla() {
  const [pestana, setPestana] = useState('buscar')
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Ventanilla</h1>
        <p className="text-sm text-slate-500">Atención presencial a clientes. Verifica siempre el documento original.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            onClick={() => setPestana(p.id)}
            className={`rounded-xl px-4 py-2 text-sm font-medium ${
              pestana === p.id
                ? 'bg-marca-600 text-white'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50'
            }`}
          >
            {p.texto}
          </button>
        ))}
      </div>
      {pestana === 'buscar' && <BuscarCliente />}
      {pestana === 'depositar' && <Depositar />}
      {pestana === 'retiro' && <EntregarRetiro />}
      {pestana === 'nuevo' && <NuevoCliente />}
      {pestana === 'cuenta' && <AbrirCuenta />}
    </div>
  )
}

// Pequena ayuda para manejar "enviando / error / resultado" en cada formulario
function useOperacion() {
  const [estado, setEstado] = useState({ cargando: false, error: '', resultado: null })
  async function ejecutar(funcion) {
    setEstado({ cargando: true, error: '', resultado: null })
    try {
      const resultado = await funcion()
      setEstado({ cargando: false, error: '', resultado })
    } catch (e) {
      setEstado({ cargando: false, error: e.message, resultado: null })
    }
  }
  return [estado, ejecutar]
}

function BuscarCliente() {
  const [cedula, setCedula] = useState('')
  const [op, ejecutar] = useOperacion()
  return (
    <Tarjeta className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); ejecutar(() => api.get(`/cajero/clientes/${cedula}`)) }}
            className="flex items-end gap-3">
        <div className="flex-1">
          <Campo etiqueta="Cédula del cliente" inputMode="numeric" required value={cedula} onChange={(e) => setCedula(e.target.value)} />
        </div>
        <Boton type="submit" cargando={op.cargando}>Buscar</Boton>
      </form>
      <Aviso>{op.error}</Aviso>
      {op.resultado && (
        <div className="space-y-3">
          <div>
            <div className="text-lg font-semibold">{op.resultado.nombre}</div>
            <div className="text-sm text-slate-500">{op.resultado.email} · celular {op.resultado.celular}</div>
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-2">Cuenta</th><th>Tipo</th><th className="text-right">Saldo</th><th className="text-right">Estado</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {op.resultado.cuentas.map((c) => (
                <tr key={c.numero}>
                  <td className="cifras py-2">{c.numero}</td>
                  <td className="capitalize">{c.tipo}</td>
                  <td className="cifras text-right">{cop(c.saldo)}</td>
                  <td className="text-right">
                    <Insignia color={c.estado === 'activa' ? 'bg-marca-50 text-marca-700' : 'bg-slate-100 text-slate-600'}>
                      {c.estado}
                    </Insignia>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Tarjeta>
  )
}

function Depositar() {
  const [datos, setDatos] = useState({ cuenta: '', monto: '' })
  const [op, ejecutar] = useOperacion()
  return (
    <Tarjeta>
      <form onSubmit={(e) => {
              e.preventDefault()
              ejecutar(() => api.post('/cajero/depositos', { cuenta: datos.cuenta.trim(), monto: Number(datos.monto) }))
            }}
            className="space-y-4">
        <Campo etiqueta="Número de cuenta (12 dígitos)" inputMode="numeric" required pattern="\d{12}"
               value={datos.cuenta} onChange={(e) => setDatos({ ...datos, cuenta: e.target.value })} />
        <Campo etiqueta="Monto en efectivo recibido" type="number" min="1000" required
               value={datos.monto} onChange={(e) => setDatos({ ...datos, monto: e.target.value })} />
        <Aviso>{op.error}</Aviso>
        {op.resultado && (
          <Aviso tipo="exito">
            Depósito de {cop(op.resultado.monto)} a {op.resultado.titular} (comprobante #{op.resultado.transaccion_id}).
          </Aviso>
        )}
        <Boton type="submit" cargando={op.cargando}>Registrar depósito</Boton>
      </form>
    </Tarjeta>
  )
}

function EntregarRetiro() {
  const [datos, setDatos] = useState({ cuenta: '', cedula: '', codigo: '' })
  const [op, ejecutar] = useOperacion()
  return (
    <Tarjeta>
      <form onSubmit={(e) => { e.preventDefault(); ejecutar(() => api.post('/cajero/retiros/canjear', datos)) }}
            className="space-y-4">
        <Aviso tipo="advertencia">
          Pide la cédula original y el código de 6 dígitos. Tras 3 intentos fallidos el código se bloquea y se avisa al
          área de fraude.
        </Aviso>
        <Campo etiqueta="Número de cuenta" inputMode="numeric" required pattern="\d{12}"
               value={datos.cuenta} onChange={(e) => setDatos({ ...datos, cuenta: e.target.value.trim() })} />
        <Campo etiqueta="Cédula (del documento físico)" inputMode="numeric" required
               value={datos.cedula} onChange={(e) => setDatos({ ...datos, cedula: e.target.value.trim() })} />
        <Campo etiqueta="Código de retiro" inputMode="numeric" required pattern="\d{6}" maxLength={6}
               value={datos.codigo} onChange={(e) => setDatos({ ...datos, codigo: e.target.value.trim() })} />
        <Aviso>{op.error}</Aviso>
        {op.resultado && (
          <Aviso tipo="exito">
            Entrega {cop(op.resultado.monto)} en efectivo a {op.resultado.titular}. (comprobante #{op.resultado.transaccion_id})
          </Aviso>
        )}
        <Boton type="submit" cargando={op.cargando}>Validar y entregar</Boton>
      </form>
    </Tarjeta>
  )
}

function NuevoCliente() {
  const vacio = { nombre: '', email: '', cedula: '', celular: '', tipo_cuenta: 'ahorros' }
  const [datos, setDatos] = useState(vacio)
  const [op, ejecutar] = useOperacion()
  const cambiar = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value })
  return (
    <Tarjeta>
      {op.resultado ? (
        <div className="space-y-4">
          <Aviso tipo="exito">Cliente creado con la cuenta {op.resultado.cuenta}.</Aviso>
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <div className="text-xs text-slate-500">Contraseña temporal (entrégala al cliente en un papel sellado)</div>
            <div className="cifras mt-1 text-2xl font-bold tracking-wider">{op.resultado.password_temporal}</div>
            <div className="mt-1 text-xs text-slate-500">No se volverá a mostrar. El cliente deberá cambiarla al entrar.</div>
          </div>
          <Boton variante="secundario" onClick={() => { setDatos(vacio); ejecutar(async () => null) }}>Crear otro</Boton>
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); ejecutar(() => api.post('/cajero/clientes', datos)) }}
              className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><Campo etiqueta="Nombre completo" required value={datos.nombre} onChange={cambiar('nombre')} /></div>
          <Campo etiqueta="Cédula" inputMode="numeric" required pattern="\d{6,10}" value={datos.cedula} onChange={cambiar('cedula')} />
          <Campo etiqueta="Celular" inputMode="numeric" required pattern="3\d{9}" value={datos.celular} onChange={cambiar('celular')} />
          <Campo etiqueta="Correo" type="email" required value={datos.email} onChange={cambiar('email')} />
          <Selector etiqueta="Tipo de cuenta" value={datos.tipo_cuenta} onChange={cambiar('tipo_cuenta')}
                    opciones={[{ valor: 'ahorros', texto: 'Ahorros' }, { valor: 'corriente', texto: 'Corriente' }]} />
          <div className="sm:col-span-2"><Aviso>{op.error}</Aviso></div>
          <div className="sm:col-span-2"><Boton type="submit" cargando={op.cargando}>Crear cliente</Boton></div>
        </form>
      )}
    </Tarjeta>
  )
}

function AbrirCuenta() {
  const [datos, setDatos] = useState({ cedula: '', tipo: 'ahorros' })
  const [op, ejecutar] = useOperacion()
  return (
    <Tarjeta>
      <form onSubmit={(e) => { e.preventDefault(); ejecutar(() => api.post('/cajero/cuentas', datos)) }} className="space-y-4">
        <Campo etiqueta="Cédula del cliente" inputMode="numeric" required value={datos.cedula}
               onChange={(e) => setDatos({ ...datos, cedula: e.target.value.trim() })} />
        <Selector etiqueta="Tipo de cuenta" value={datos.tipo} onChange={(e) => setDatos({ ...datos, tipo: e.target.value })}
                  opciones={[{ valor: 'ahorros', texto: 'Ahorros' }, { valor: 'corriente', texto: 'Corriente' }]} />
        <Aviso>{op.error}</Aviso>
        {op.resultado && <Aviso tipo="exito">Cuenta {op.resultado.cuenta} abierta a {op.resultado.titular}.</Aviso>}
        <Boton type="submit" cargando={op.cargando}>Abrir cuenta</Boton>
      </form>
    </Tarjeta>
  )
}
