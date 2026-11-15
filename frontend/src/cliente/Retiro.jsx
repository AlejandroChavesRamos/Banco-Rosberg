// Retiro sin tarjeta: el cliente genera un codigo y lo canjea en ventanilla
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Aviso, Boton, Campo, Insignia, Selector, Tarjeta } from '../componentes/ui'
import { cop, enmascarar, fechaHora } from '../formato'

const ESTADO_CODIGO = {
  activo: { texto: 'Vigente', color: 'text-marca-700 bg-marca-50 dark:text-marca-300 dark:bg-marca-950' },
  usado: { texto: 'Usado', color: 'text-slate-600 bg-slate-100 dark:text-slate-300 dark:bg-slate-800' },
  vencido: { texto: 'Vencido', color: 'text-slate-500 bg-slate-100 dark:bg-slate-800' },
  cancelado: { texto: 'Cancelado', color: 'text-slate-500 bg-slate-100 dark:bg-slate-800' },
  bloqueado: { texto: 'Bloqueado', color: 'text-red-700 bg-red-50 dark:text-red-300 dark:bg-red-950' },
}

export default function Retiro() {
  const [cuentas, setCuentas] = useState([])
  const [cuenta, setCuenta] = useState('')
  const [monto, setMonto] = useState('')
  const [codigo, setCodigo] = useState(null) // el codigo recien generado (solo se muestra una vez)
  const [historial, setHistorial] = useState([])
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    api.get('/cuentas').then((lista) => {
      const activas = lista.filter((c) => c.estado === 'activa')
      setCuentas(activas)
      if (activas.length) setCuenta(activas[0].numero)
    })
    cargarHistorial()
  }, [])

  function cargarHistorial() {
    api.get('/retiros/codigos').then(setHistorial).catch(() => {})
  }

  async function generar(evento) {
    evento.preventDefault()
    setError('')
    setCargando(true)
    try {
      const r = await api.post('/retiros/codigo', { cuenta, monto: Number(monto) })
      setCodigo(r)
      setMonto('')
      cargarHistorial()
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Retirar sin tarjeta</h1>
        <p className="text-sm text-slate-500">Genera un código y preséntalo con tu cédula en cualquier oficina.</p>
      </div>

      {/* Dos columnas en computador: generar a la izquierda, historial a la derecha */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
      {codigo ? (
        <CodigoGenerado c={codigo} onCerrar={() => setCodigo(null)} />
      ) : (
        <Tarjeta>
          <form onSubmit={generar} className="space-y-4">
            <Selector
              etiqueta="Cuenta"
              value={cuenta}
              onChange={(e) => setCuenta(e.target.value)}
              opciones={cuentas.map((c) => ({ valor: c.numero, texto: `Ahorros ${enmascarar(c.numero)} · ${cop(c.saldo)}` }))}
            />
            <Campo etiqueta="Monto" type="number" inputMode="numeric" min="10000" max="2000000" step="1000" required
                   ayuda="Máximo $ 2.000.000 por código" value={monto} onChange={(e) => setMonto(e.target.value)} />
            <Aviso>{error}</Aviso>
            <Boton type="submit" cargando={cargando} className="w-full">Generar código</Boton>
          </form>
        </Tarjeta>
      )}

      {historial.length === 0 ? (
        <Tarjeta className="text-sm text-slate-500">Aún no has generado códigos de retiro.</Tarjeta>
      ) : (
        <Tarjeta className="p-0">
          <h2 className="px-5 pt-5 font-semibold">Códigos recientes</h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {historial.map((h) => (
              <li key={h.id} className="flex items-center justify-between px-5 py-3.5">
                <div>
                  <div className="cifras text-sm font-medium">{cop(h.monto)}</div>
                  <div className="text-xs text-slate-500">{fechaHora(h.creado_en)}</div>
                </div>
                <Insignia color={ESTADO_CODIGO[h.estado].color}>{ESTADO_CODIGO[h.estado].texto}</Insignia>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}
      </div>
    </div>
  )
}

// El codigo en grande, con cuenta regresiva hasta que venza
function CodigoGenerado({ c, onCerrar }) {
  const [restante, setRestante] = useState('')

  useEffect(() => {
    function actualizar() {
      const segundos = Math.max(0, Math.floor((new Date(c.expira_en) - new Date()) / 1000))
      setRestante(`${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`)
    }
    actualizar()
    const reloj = setInterval(actualizar, 1000) // cada segundo
    return () => clearInterval(reloj) // al salir de la pantalla, detener el reloj
  }, [c.expira_en])

  return (
    <Tarjeta className="space-y-4 text-center">
      <p className="text-sm text-slate-500">Tu código para retirar {cop(c.monto)}</p>
      <div className="cifras text-5xl font-bold tracking-[0.3em] text-marca-600 dark:text-marca-400">{c.codigo}</div>
      <p className="text-sm">
        Vence en <span className="cifras font-semibold">{restante}</span>
      </p>
      <Aviso tipo="advertencia">
        Este código solo se muestra una vez. No lo compartas: el banco nunca te lo pedirá por teléfono.
      </Aviso>
      <Boton variante="secundario" onClick={onCerrar} className="w-full">Ya lo anoté</Boton>
    </Tarjeta>
  )
}
