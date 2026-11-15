// =====================================================================
// Enviar dinero en 3 pasos:
//   1. Datos (cuenta origen, destino, monto)
//   2. Confirmar: se muestra a quien le llega (nombre enmascarado)
//   3. Resultado: exitosa, en revision o bloqueada (decide el motor antifraude)
// Si se llega desde "Envio rapido" del Inicio, los datos vienen ya puestos
// y se salta directo a la confirmacion.
// =====================================================================
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, nuevaClave } from '../api'
import { Aviso, Boton, Campo, Selector, Tarjeta } from '../componentes/ui'
import { cop, enmascarar } from '../formato'

export default function Transferir() {
  const ubicacion = useLocation()
  const desdeEnvioRapido = useRef(ubicacion.state) // datos que mando el Inicio (si hay)
  const [paso, setPaso] = useState(1)
  const [cuentas, setCuentas] = useState([])
  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState(desdeEnvioRapido.current?.destino ?? '')
  const [monto, setMonto] = useState(desdeEnvioRapido.current?.monto ?? '')
  const [destinatario, setDestinatario] = useState(null)
  const [clave, setClave] = useState(null) // Idempotency-Key de ESTA transferencia
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    api.get('/cuentas').then((lista) => {
      const activas = lista.filter((c) => c.estado === 'activa')
      setCuentas(activas)
      const preferida = activas.find((c) => c.numero === desdeEnvioRapido.current?.origen)
      setOrigen((preferida ?? activas[0])?.numero ?? '')
      // Venia del Envio rapido: buscar el destinatario de una vez
      if (desdeEnvioRapido.current?.destino) {
        buscarDestinatario(desdeEnvioRapido.current.destino)
        desdeEnvioRapido.current = null
      }
    })
  }, [])

  const saldoOrigen = cuentas.find((c) => c.numero === origen)?.saldo ?? 0

  async function buscarDestinatario(valor) {
    setError('')
    setCargando(true)
    try {
      const d = await api.get(`/transferencias/destinatario?valor=${encodeURIComponent(valor.trim())}`)
      setDestinatario(d)
      // La clave se crea UNA vez por transferencia: si el usuario pulsa
      // "Confirmar" dos veces o la red falla y reintenta, el backend
      // reconoce la misma clave y no cobra dos veces.
      setClave(nuevaClave())
      setPaso(2)
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  // Paso 2 -> 3: enviar la transferencia
  async function confirmar() {
    setError('')
    setCargando(true)
    try {
      const r = await api.post('/transferencias', { cuenta_origen: origen, destino: destino.trim(), monto: Number(monto) }, { clave })
      setResultado(r)
      setPaso(3)
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  function otraTransferencia() {
    setPaso(1)
    setDestino('')
    setMonto('')
    setDestinatario(null)
    setResultado(null)
    api.get('/cuentas').then((lista) => setCuentas(lista.filter((c) => c.estado === 'activa')))
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Enviar dinero</h1>
        <p className="text-sm text-slate-500">A cualquier cuenta de Banco Rosberg, con su número o su llave.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div>
          <Pasos actual={paso} />

          {paso === 1 && (
            <Tarjeta>
              <form onSubmit={(e) => { e.preventDefault(); buscarDestinatario(destino) }} className="grid gap-5 md:grid-cols-2">
                <div className="md:col-span-2">
                  <Selector
                    etiqueta="Desde"
                    value={origen}
                    onChange={(e) => setOrigen(e.target.value)}
                    opciones={cuentas.map((c) => ({ valor: c.numero, texto: `Ahorros ${enmascarar(c.numero)} · ${cop(c.saldo)}` }))}
                  />
                </div>
                <Campo etiqueta="Para" required placeholder="Celular, correo o número de cuenta"
                       ayuda="La llave (celular o correo) o el número de cuenta del destinatario"
                       value={destino} onChange={(e) => setDestino(e.target.value)} />
                <Campo etiqueta="Monto" type="number" inputMode="numeric" min="1000" step="1" required placeholder="50000"
                       ayuda={`Disponible: ${cop(saldoOrigen)}`} value={monto} onChange={(e) => setMonto(e.target.value)} />
                <div className="md:col-span-2"><Aviso>{error}</Aviso></div>
                <div className="md:col-span-2">
                  <Boton type="submit" cargando={cargando} disabled={!origen}>Continuar</Boton>
                </div>
              </form>
            </Tarjeta>
          )}

          {paso === 2 && destinatario && (
            <Tarjeta className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <p className="text-sm text-slate-500">Vas a enviar</p>
                  <div className="cifras text-4xl font-bold tracking-tight">{cop(monto)}</div>
                  <p className="mt-1 text-sm text-slate-500">desde Ahorros {enmascarar(origen)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-800/60">
                  <div className="text-xs text-slate-500">A</div>
                  <div className="text-lg font-semibold">{destinatario.titular}</div>
                  <div className="text-sm text-slate-500">Cuenta de {destinatario.tipo} {destinatario.cuenta}</div>
                </div>
              </div>
              <p className="text-sm text-slate-500">
                Verifica que el nombre corresponda a la persona. Por tu seguridad solo mostramos parte del nombre.
              </p>
              <Aviso>{error}</Aviso>
              <div className="flex gap-3">
                <Boton variante="secundario" onClick={() => setPaso(1)} disabled={cargando}>Volver</Boton>
                <Boton onClick={confirmar} cargando={cargando}>Confirmar envío</Boton>
              </div>
            </Tarjeta>
          )}

          {paso === 3 && <Resultado r={resultado} onOtra={otraTransferencia} />}
        </div>

        {/* Columna lateral de ayuda */}
        <Tarjeta className="h-fit space-y-4 text-sm">
          <h2 className="font-semibold">Envía seguro</h2>
          <Consejo icono="⚿" titulo="Usa llaves">
            Pide el celular o correo registrado del destinatario: no necesitas su número de cuenta.
          </Consejo>
          <Consejo icono="👁" titulo="Revisa el nombre">
            Antes de confirmar te mostramos parte del nombre del titular. Si no coincide, no envíes.
          </Consejo>
          <Consejo icono="⏸" titulo="Operaciones en revisión">
            Si algo parece inusual, tu envío queda en revisión y el dinero no sale hasta que lo verifiquemos.
          </Consejo>
        </Tarjeta>
      </div>
    </div>
  )
}

function Pasos({ actual }) {
  const nombres = ['Datos', 'Confirmar', 'Listo']
  return (
    <ol className="mb-5 flex items-center gap-3 text-sm">
      {nombres.map((n, i) => (
        <li key={n} className="flex items-center gap-2">
          <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${
            i + 1 <= actual ? 'bg-marca-600 text-white' : 'bg-slate-200 text-slate-500 dark:bg-slate-800'
          }`}>{i + 1}</span>
          <span className={i + 1 === actual ? 'font-semibold' : 'text-slate-500'}>{n}</span>
          {i < nombres.length - 1 && <span className="h-px w-8 bg-slate-300 dark:bg-slate-700" />}
        </li>
      ))}
    </ol>
  )
}

function Consejo({ icono, titulo, children }) {
  return (
    <div className="flex gap-3">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300">{icono}</span>
      <div>
        <div className="font-medium">{titulo}</div>
        <div className="text-slate-500">{children}</div>
      </div>
    </div>
  )
}

// Resultado segun lo que decidio el motor antifraude
function Resultado({ r, onOtra }) {
  const estilos = {
    aprobada: { icono: '✓', titulo: '¡Listo!', color: 'bg-marca-100 text-marca-700 dark:bg-marca-950 dark:text-marca-300' },
    retenida: { icono: '⏸', titulo: 'En revisión', color: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300' },
    bloqueada: { icono: '⛔', titulo: 'Operación bloqueada', color: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300' },
  }
  const e = estilos[r.estado] ?? estilos.aprobada
  return (
    <Tarjeta className="py-10 text-center">
      <div className={`mx-auto mb-4 grid h-20 w-20 place-items-center rounded-full text-4xl ${e.color}`}>{e.icono}</div>
      <h2 className="text-2xl font-bold">{e.titulo}</h2>
      {r.monto && <div className="cifras mt-2 text-3xl font-bold">{cop(r.monto)}</div>}
      {r.destinatario && <p className="mt-1 text-slate-500">para {r.destinatario}</p>}
      <p className="mx-auto mt-4 max-w-sm text-sm text-slate-500">{r.mensaje}</p>
      <p className="mt-2 text-xs text-slate-400">Comprobante #{r.transaccion_id}</p>
      <div className="mt-8 flex justify-center gap-3">
        <Boton onClick={onOtra}>Hacer otra transferencia</Boton>
        <Link to="/app" className="rounded-xl px-4 py-2.5 text-sm font-semibold text-marca-600 hover:bg-marca-50 dark:hover:bg-marca-950">
          Volver al inicio
        </Link>
      </div>
    </Tarjeta>
  )
}
