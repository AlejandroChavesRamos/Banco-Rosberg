// =====================================================================
// Inicio del cliente (pensado para computador):
//   Columna izquierda: sus cuentas, resumen del mes y envio rapido.
//   Columna derecha:  tabla de movimientos de la cuenta seleccionada.
// En una ventana angosta las columnas se apilan una debajo de otra.
// =====================================================================
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Girando, Insignia, Tarjeta } from '../componentes/ui'
import { ESTADOS, cop, enmascarar, fechaHora } from '../formato'
import { useSesion } from '../sesion'

const TIPOS = { deposito: 'Depósito', retiro: 'Retiro', transferencia: 'Transferencia' }

export default function Inicio() {
  const { usuario } = useSesion()
  const [cuentas, setCuentas] = useState([])
  const [seleccionada, setSeleccionada] = useState(null) // numero de la cuenta que se esta viendo
  const [detalle, setDetalle] = useState(null) // movimientos de esa cuenta
  const [error, setError] = useState('')
  const [abriendo, setAbriendo] = useState(false)

  // useEffect: codigo que corre al abrir la pantalla (traer las cuentas)
  useEffect(() => {
    cargarCuentas()
  }, [])

  // Cada vez que cambia la cuenta seleccionada, traer sus movimientos
  useEffect(() => {
    if (!seleccionada) return
    setDetalle(null)
    api.get(`/cuentas/${seleccionada}/movimientos`).then(setDetalle).catch((e) => setError(e.message))
  }, [seleccionada])

  async function cargarCuentas() {
    try {
      const lista = await api.get('/cuentas')
      setCuentas(lista)
      if (lista.length && !seleccionada) setSeleccionada(lista[0].numero)
    } catch (e) {
      setError(e.message)
    }
  }

  async function abrirCuenta() {
    setAbriendo(true)
    try {
      const r = await api.post('/cuentas', { tipo: 'ahorros' })
      await cargarCuentas()
      setSeleccionada(r.cuenta)
    } catch (e) {
      setError(e.message)
    } finally {
      setAbriendo(false)
    }
  }

  const primerNombre = usuario.nombre.split(' ')[0]
  const total = cuentas.reduce((suma, c) => suma + Number(c.saldo), 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500 dark:text-slate-400">Hola, {primerNombre}</p>
          <h1 className="text-2xl font-bold tracking-tight">Resumen de tus cuentas</h1>
        </div>
        {cuentas.length > 1 && (
          <div className="text-right">
            <div className="text-xs text-slate-500">Saldo total</div>
            <div className="cifras text-2xl font-bold">{cop(total)}</div>
          </div>
        )}
      </div>

      <Aviso>{error}</Aviso>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        {/* ----------------------------- Columna izquierda */}
        <div className="space-y-6">
          {cuentas.map((c) => (
            <TarjetaCuenta key={c.numero} c={c} activa={c.numero === seleccionada} onClick={() => setSeleccionada(c.numero)} />
          ))}
          {cuentas.length > 0 && cuentas.length < 3 && (
            <Boton variante="secundario" className="w-full" cargando={abriendo} onClick={abrirCuenta}>
              + Abrir otra cuenta de ahorros
            </Boton>
          )}
          {detalle && <ResumenMes movimientos={detalle.movimientos} />}
          {cuentas.length > 0 && <EnvioRapido cuentas={cuentas} origen={seleccionada} />}
        </div>

        {/* ------------------------------ Columna derecha */}
        <Tarjeta className="p-0">
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
            <h2 className="font-semibold">Movimientos</h2>
            {detalle && <span className="text-sm text-slate-500">Cuenta {enmascarar(detalle.cuenta)} · últimos 50</span>}
          </div>
          {!detalle ? (
            <div className="flex justify-center p-12 text-marca-600"><Girando /></div>
          ) : detalle.movimientos.length === 0 ? (
            <p className="p-6 text-sm text-slate-500">Aún no tienes movimientos en esta cuenta.</p>
          ) : (
            <TablaMovimientos movimientos={detalle.movimientos} />
          )}
        </Tarjeta>
      </div>
    </div>
  )
}

function TarjetaCuenta({ c, activa, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-3xl p-6 text-left text-white shadow-lg transition ${
        activa ? 'bg-gradient-to-br from-marca-500 to-marca-800 ring-4 ring-marca-200 dark:ring-marca-900' : 'bg-gradient-to-br from-slate-500 to-slate-700 opacity-80 hover:opacity-100'
      }`}
    >
      <div className="flex items-center justify-between text-sm text-white/80">
        <span>Cuenta de {c.tipo}</span>
        <span className="cifras">{enmascarar(c.numero)}</span>
      </div>
      <div className="mt-8 text-xs text-white/70">Saldo disponible</div>
      <div className="cifras text-3xl font-bold tracking-tight">{cop(c.saldo)}</div>
      {c.estado !== 'activa' && <div className="mt-3 inline-block rounded-full bg-white/20 px-2 py-0.5 text-xs">Cuenta {c.estado}</div>}
    </button>
  )
}

// Entradas y salidas del mes actual (solo movimientos que si se aplicaron)
function ResumenMes({ movimientos }) {
  const ahora = new Date()
  const delMes = movimientos.filter((m) => {
    const f = new Date(m.fecha)
    return m.estado === 'aprobada' && f.getMonth() === ahora.getMonth() && f.getFullYear() === ahora.getFullYear()
  })
  const entradas = delMes.filter((m) => m.sentido === 'entrada').reduce((s, m) => s + Number(m.monto), 0)
  const salidas = delMes.filter((m) => m.sentido === 'salida').reduce((s, m) => s + Number(m.monto), 0)
  const enRevision = movimientos.filter((m) => m.estado === 'retenida').length
  const mes = ahora.toLocaleString('es-CO', { month: 'long' })

  return (
    <Tarjeta className="space-y-3">
      <h2 className="font-semibold">Este mes <span className="font-normal capitalize text-slate-500">({mes})</span></h2>
      <div className="flex justify-between text-sm">
        <span className="text-slate-500">↙ Entradas</span>
        <span className="cifras font-semibold text-marca-600 dark:text-marca-400">+{cop(entradas)}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-slate-500">↗ Salidas</span>
        <span className="cifras font-semibold">−{cop(salidas)}</span>
      </div>
      {enRevision > 0 && (
        <Aviso tipo="advertencia">Tienes {enRevision} operación(es) en revisión por seguridad.</Aviso>
      )}
    </Tarjeta>
  )
}

// Envio rapido: lleva a la pantalla de Enviar con los datos ya puestos
function EnvioRapido({ origen }) {
  const navegar = useNavigate()
  const [destino, setDestino] = useState('')
  const [monto, setMonto] = useState('')
  return (
    <Tarjeta>
      <h2 className="mb-3 font-semibold">Envío rápido</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          // "state" viaja con la navegacion: la pantalla Enviar lo recibe y salta a confirmar
          navegar('/app/transferir', { state: { origen, destino, monto } })
        }}
        className="space-y-3"
      >
        <Campo etiqueta="Para" required placeholder="Celular, correo o cuenta" value={destino} onChange={(e) => setDestino(e.target.value)} />
        <Campo etiqueta="Monto" type="number" min="1000" required placeholder="50000" value={monto} onChange={(e) => setMonto(e.target.value)} />
        <Boton type="submit" className="w-full">Continuar</Boton>
      </form>
    </Tarjeta>
  )
}

function TablaMovimientos({ movimientos }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-6 py-3 font-medium">Fecha</th>
            <th className="py-3 font-medium">Descripción</th>
            <th className="py-3 font-medium">Estado</th>
            <th className="px-6 py-3 text-right font-medium">Valor</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {movimientos.map((m) => {
            const entrada = m.sentido === 'entrada'
            const estado = ESTADOS[m.estado]
            const noAplicada = m.estado !== 'aprobada' // retenida/bloqueada: el dinero no se movio
            return (
              <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                <td className="whitespace-nowrap px-6 py-3 text-slate-500">{fechaHora(m.fecha)}</td>
                <td className="py-3">
                  <div className="flex items-center gap-3">
                    <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${
                      entrada ? 'bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                    }`}>
                      {entrada ? '↙' : '↗'}
                    </span>
                    <span className="font-medium">
                      {TIPOS[m.tipo]}{' '}
                      {m.contraparte && <span className="font-normal text-slate-500">{entrada ? 'de' : 'a'} {m.contraparte}</span>}
                    </span>
                  </div>
                </td>
                <td className="py-3"><Insignia color={estado.color}>{estado.texto}</Insignia></td>
                <td className={`cifras whitespace-nowrap px-6 py-3 text-right font-semibold ${
                  noAplicada ? 'text-slate-400 line-through' : entrada ? 'text-marca-600 dark:text-marca-400' : ''
                }`}>
                  {entrada ? '+' : '−'}{cop(m.monto)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
