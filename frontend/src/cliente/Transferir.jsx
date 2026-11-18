// =====================================================================
// Enviar dinero en 3 pasos:
//   1. Datos (cuenta origen, destino, monto y un mensaje opcional, como en Nequi)
//   2. Confirmar: se muestra a quien le llega (nombre enmascarado)
//   3. Resultado: exitosa, en revision o bloqueada (decide el motor antifraude)
// Si se llega desde "Envio rapido" del Inicio, los datos vienen ya puestos
// y se salta directo a la confirmacion.
// =====================================================================
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, nuevaClave } from '../api'
import { CampoCodigo } from '../componentes/DosPasos'
import Icono from '../componentes/Icono'
import { Aviso, Boton, Campo, Selector, Tarjeta } from '../componentes/ui'
import { cop, enmascarar, fechaHora } from '../formato'

export default function Transferir() {
  const ubicacion = useLocation()
  const desdeEnvioRapido = useRef(ubicacion.state) // datos que mando el Inicio (si hay)
  const [paso, setPaso] = useState(1)
  const [cuentas, setCuentas] = useState([])
  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState(desdeEnvioRapido.current?.destino ?? '')
  const [monto, setMonto] = useState(desdeEnvioRapido.current?.monto ?? '')
  const [mensaje, setMensaje] = useState('') // nota para quien recibe ("Para el almuerzo")
  const [destinatario, setDestinatario] = useState(null)
  const [clave, setClave] = useState(null) // Idempotency-Key de ESTA transferencia
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  const [pideCodigo, setPideCodigo] = useState(false) // el banco exige 2FA para este monto
  const [codigo2fa, setCodigo2fa] = useState('')

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
      const cuerpo = { cuenta_origen: origen, destino: destino.trim(), monto: Number(monto) }
      if (mensaje.trim()) cuerpo.mensaje = mensaje.trim()
      if (pideCodigo) cuerpo.codigo_2fa = codigo2fa
      const r = await api.post('/transferencias', cuerpo, { clave })
      setResultado(r)
      setPaso(3)
    } catch (e) {
      // 428: el banco exige el codigo de la app autenticadora para este monto
      if (e.status === 428) setPideCodigo(true)
      setCodigo2fa('')
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  function otraTransferencia() {
    setPaso(1)
    setPideCodigo(false)
    setCodigo2fa('')
    setDestino('')
    setMonto('')
    setMensaje('')
    setDestinatario(null)
    setResultado(null)
    api.get('/cuentas').then((lista) => setCuentas(lista.filter((c) => c.estado === 'activa')))
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Enviar dinero</h1>
        <p className="text-sm text-slate-500">A cualquier cuenta de Banco Rosberg, con su número o su llave.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div>
          <div className="no-imprimir"><Pasos actual={paso} /></div>

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
                <div className="md:col-span-2">
                  <Campo etiqueta="Mensaje (opcional)" maxLength={140} placeholder="Ej.: Para el almuerzo 🍔"
                         ayuda={`Lo verá quien recibe el dinero. ${mensaje.length}/140`}
                         value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
                </div>
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
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs text-slate-500">A</div>
                  <div className="text-lg font-semibold">{destinatario.titular}</div>
                  <div className="text-sm text-slate-500">Cuenta de {destinatario.tipo} {destinatario.cuenta}</div>
                </div>
              </div>
              {mensaje.trim() && (
                <div className="flex items-start gap-3 rounded-xl bg-marca-50 p-4 text-sm">
                  <Icono nombre="chat" className="mt-0.5 h-4 w-4 text-marca-600" />
                  <span className="italic text-marca-800">“{mensaje.trim()}”</span>
                </div>
              )}
              <p className="text-sm text-slate-500">
                Verifica que el nombre corresponda a la persona. Por tu seguridad solo mostramos parte del nombre.
              </p>
              {pideCodigo && (
                <div className="max-w-xs space-y-2">
                  <div className="text-sm font-medium">Código de tu app autenticadora</div>
                  <CampoCodigo valor={codigo2fa} onCambio={setCodigo2fa} autoFocus />
                </div>
              )}
              <Aviso tipo={pideCodigo && error.startsWith('Escribe') ? 'advertencia' : 'error'}>{error}</Aviso>
              <div className="flex gap-3">
                <Boton variante="secundario" onClick={() => setPaso(1)} disabled={cargando}>Volver</Boton>
                <Boton onClick={confirmar} cargando={cargando} disabled={pideCodigo && codigo2fa.length !== 6}>Confirmar envío</Boton>
              </div>
            </Tarjeta>
          )}

          {paso === 3 && <Resultado r={resultado} onOtra={otraTransferencia} />}
        </div>

        {/* Columna lateral de ayuda */}
        <Tarjeta className="no-imprimir h-fit space-y-4 text-sm">
          <h2 className="text-lg font-semibold text-marca-700">Envía seguro</h2>
          <Consejo icono="llave" titulo="Usa llaves">
            Pide el celular o correo registrado del destinatario: no necesitas su número de cuenta.
          </Consejo>
          <Consejo icono="ojo" titulo="Revisa el nombre">
            Antes de confirmar te mostramos parte del nombre del titular. Si no coincide, no envíes.
          </Consejo>
          <Consejo icono="pausa" titulo="Operaciones en revisión">
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
            i + 1 <= actual ? 'bg-marca-600 text-white' : 'bg-slate-200 text-slate-500'
          }`}>{i + 1}</span>
          <span className={i + 1 === actual ? 'font-semibold' : 'text-slate-500'}>{n}</span>
          {i < nombres.length - 1 && <span className="h-px w-8 bg-slate-300" />}
        </li>
      ))}
    </ol>
  )
}

function Consejo({ icono, titulo, children }) {
  return (
    <div className="flex gap-3">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-marca-50 text-marca-700"><Icono nombre={icono} className="h-4 w-4" /></span>
      <div>
        <div className="font-medium">{titulo}</div>
        <div className="text-slate-500">{children}</div>
      </div>
    </div>
  )
}

// Resultado segun lo que decidio el motor antifraude, con su comprobante
function Resultado({ r, onOtra }) {
  const estilos = {
    aprobada: { icono: 'check', titulo: 'Transferencia exitosa', color: 'bg-marca-100 text-marca-700' },
    retenida: { icono: 'pausa', titulo: 'En revisión', color: 'bg-amber-100 text-amber-800' },
    bloqueada: { icono: 'bloqueo', titulo: 'Operación bloqueada', color: 'bg-red-100 text-red-700' },
  }
  const e = estilos[r.estado] ?? estilos.aprobada
  return (
    <Tarjeta className="p-0">
      <div className="px-6 pb-6 pt-10 text-center">
        <div className={`confirmado mx-auto mb-4 grid h-20 w-20 place-items-center rounded-full ${e.color}`}>
          {r.estado === 'aprobada' ? (
            // Circulo y check que se dibujan solos
            <svg viewBox="0 0 24 24" className="check-dibujado h-12 w-12" fill="none" stroke="currentColor" strokeWidth="1.8"
                 strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle className="check-circulo" cx="12" cy="12" r="10" />
              <path d="m7.5 12.5 3 3 6-6.5" />
            </svg>
          ) : (
            <Icono nombre={e.icono} className="h-10 w-10" />
          )}
        </div>
        <h2 className="text-2xl font-bold text-marca-700">{e.titulo}</h2>
        {r.monto && <div className="cifras mt-2 font-titulo text-4xl font-bold text-marca-900">{cop(r.monto)}</div>}
        <p className="mx-auto mt-3 max-w-sm text-sm text-slate-500">{r.mensaje}</p>
      </div>

      {/* Comprobante. En una transferencia repetida (doble clic) el backend solo devuelve el numero. */}
      <dl className="mx-6 divide-y divide-dashed divide-marca-200 border-y border-dashed border-marca-200 text-sm">
        <Linea etiqueta="Comprobante">#{r.transaccion_id}</Linea>
        {r.fecha && <Linea etiqueta="Fecha">{fechaHora(r.fecha)}</Linea>}
        {r.cuenta_origen && <Linea etiqueta="Desde">Cuenta {r.cuenta_origen}</Linea>}
        {r.destinatario && <Linea etiqueta="Para">{r.destinatario}</Linea>}
        {r.cuenta_destino && <Linea etiqueta="Cuenta destino">{r.cuenta_destino}</Linea>}
        {r.mensaje_envio && <Linea etiqueta="Mensaje"><span className="font-normal italic">“{r.mensaje_envio}”</span></Linea>}
      </dl>
      <p className="px-6 pt-4 text-center text-xs text-slate-400">
        Banco Rosberg. Proyecto académico: este comprobante no tiene validez legal.
      </p>

      <div className="no-imprimir flex flex-wrap justify-center gap-3 p-6">
        <Boton variante="secundario" onClick={() => window.print()}>
          <Icono nombre="imprimir" className="h-4 w-4" />
          Imprimir o guardar PDF
        </Boton>
        <Boton onClick={onOtra}>Hacer otra transferencia</Boton>
        <Link to="/app" className="boton-vivo rounded-xl px-4 py-2.5 text-sm font-semibold text-marca-700 hover:bg-marca-50">
          Volver al inicio
        </Link>
      </div>
    </Tarjeta>
  )
}

function Linea({ etiqueta, children }) {
  return (
    <div className="flex justify-between gap-6 py-3">
      <dt className="text-slate-500">{etiqueta}</dt>
      <dd className="cifras text-right font-medium text-marca-900">{children}</dd>
    </div>
  )
}
