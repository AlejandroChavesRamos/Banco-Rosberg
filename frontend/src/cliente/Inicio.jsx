// =====================================================================
// Inicio del cliente (pensado para computador):
//   Arriba: saludo, saldo total (con el "ojo" para ocultarlo) y accesos rapidos.
//   Columna izquierda: sus cuentas, resumen del mes y envio rapido.
//   Columna derecha:  grafica de los ultimos meses y tabla de movimientos.
// En una ventana angosta las columnas se apilan una debajo de otra.
// =====================================================================
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useAviso } from '../componentes/Avisos'
import Icono from '../componentes/Icono'
import { Dinero, useSaldoOculto } from '../componentes/Saldo'
import { Aviso, Boton, Campo, Cargando, Dialogo, EstadoVacio, Insignia, Selector, Silueta, Tarjeta } from '../componentes/ui'
import { ESTADOS, cop, enmascarar, fechaHora } from '../formato'
import { useSesion } from '../sesion'

const TIPOS = { deposito: 'Depósito', retiro: 'Retiro', transferencia: 'Transferencia' }

const ACCESOS = [
  { a: '/app/transferir', texto: 'Enviar dinero', icono: 'enviar' },
  { a: '/app/retiro', texto: 'Retirar sin tarjeta', icono: 'codigo' },
  { a: '/app/metas', texto: 'Metas de ahorro', icono: 'meta' },
  { a: '/app/llaves', texto: 'Mis llaves', icono: 'llave' },
]

function saludo() {
  const hora = new Date().getHours()
  if (hora < 12) return 'Buenos días'
  if (hora < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Inicio() {
  const { usuario } = useSesion()
  const { oculto, alternar } = useSaldoOculto()
  const [cuentas, setCuentas] = useState(null) // null = todavia cargando
  const [seleccionada, setSeleccionada] = useState(null) // numero de la cuenta que se esta viendo
  const [detalle, setDetalle] = useState(null) // movimientos de esa cuenta
  const [error, setError] = useState('')
  const [abriendo, setAbriendo] = useState(false)
  const [cerrando, setCerrando] = useState(null) // cuenta que se va a cerrar (abre el dialogo)
  const [filtro, setFiltro] = useState({ desde: '', hasta: '' }) // rango de fechas del extracto

  // useEffect: codigo que corre al abrir la pantalla (traer las cuentas)
  useEffect(() => {
    cargarCuentas()
  }, [])

  // Cada vez que cambia la cuenta seleccionada, traer sus movimientos
  useEffect(() => {
    if (!seleccionada) return
    setDetalle(null)
    // Sin fechas: los ultimos 50. Con fechas: hasta 500 movimientos de ese rango.
    const parametros = new URLSearchParams()
    if (filtro.desde) parametros.set('desde', filtro.desde)
    if (filtro.hasta) parametros.set('hasta', filtro.hasta)
    if (filtro.desde || filtro.hasta) parametros.set('limite', '500')
    api.get(`/cuentas/${seleccionada}/movimientos?${parametros}`).then(setDetalle).catch((e) => setError(e.message))
  }, [seleccionada, filtro])

  const conFiltro = Boolean(filtro.desde || filtro.hasta)

  async function cargarCuentas(preferida) {
    try {
      const lista = await api.get('/cuentas')
      setCuentas(lista)
      const sigueExistiendo = lista.some((c) => c.numero === (preferida ?? seleccionada))
      setSeleccionada(sigueExistiendo ? (preferida ?? seleccionada) : lista[0]?.numero ?? null)
    } catch (e) {
      setError(e.message)
    }
  }

  async function abrirCuenta() {
    setAbriendo(true)
    try {
      const r = await api.post('/cuentas', { tipo: 'ahorros' })
      await cargarCuentas(r.cuenta)
    } catch (e) {
      setError(e.message)
    } finally {
      setAbriendo(false)
    }
  }

  const primerNombre = usuario.nombre.split(' ')[0]
  const lista = cuentas ?? []
  const total = lista.reduce((suma, c) => suma + Number(c.saldo), 0)
  const activas = lista.filter((c) => c.estado === 'activa')

  return (
    <div className="space-y-8">
      {/* Saludo y saldo total */}
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-sm text-slate-500">{saludo()}, {primerNombre}</p>
          <h1 className="text-3xl font-bold tracking-tight text-marca-700">Resumen de tus cuentas</h1>
        </div>
        <div className="flex items-center gap-4 text-right">
          <div>
            <div className="text-xs text-slate-500">{lista.length > 1 ? 'Saldo total' : 'Tu saldo'}</div>
            <div className="font-titulo text-3xl font-bold tracking-tight text-marca-800">
              {cuentas ? <Dinero valor={total} /> : <Silueta className="ml-auto h-8 w-40" />}
            </div>
          </div>
          <button
            onClick={alternar}
            aria-pressed={oculto}
            className="grid h-11 w-11 place-items-center rounded-full bg-white text-marca-700 ring-1 ring-marca-200 hover:bg-marca-50"
            title={oculto ? 'Mostrar saldos' : 'Ocultar saldos'}
            aria-label={oculto ? 'Mostrar saldos' : 'Ocultar saldos'}
          >
            <Icono nombre={oculto ? 'ojoCerrado' : 'ojo'} />
          </button>
        </div>
      </div>

      {/* Accesos rapidos */}
      <nav className="grid grid-cols-2 gap-4 md:grid-cols-4" aria-label="Accesos rápidos">
        {ACCESOS.map((a) => (
          <Link
            key={a.a}
            to={a.a}
            className="boton-vivo group flex items-center gap-4 rounded-3xl bg-white p-5 shadow-sm shadow-marca-900/5 ring-1 ring-marca-100 hover:ring-marca-300"
          >
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-marca-700 text-white transition-colors group-hover:bg-oro group-hover:text-marca-900">
              <Icono nombre={a.icono} className="h-6 w-6" />
            </span>
            <span className="font-semibold text-marca-800">{a.texto}</span>
          </Link>
        ))}
      </nav>

      <Aviso>{error}</Aviso>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        {/* ----------------------------- Columna izquierda */}
        <div className="space-y-6">
          {!cuentas && <Silueta className="h-44 rounded-3xl" />}
          {lista.map((c) => (
            <TarjetaCuenta
              key={c.numero}
              c={c}
              activa={c.numero === seleccionada}
              onClick={() => setSeleccionada(c.numero)}
              puedeCerrar={activas.length > 1 && c.estado === 'activa'}
              onCerrar={() => setCerrando(c)}
            />
          ))}
          {lista.length > 0 && lista.length < 3 && (
            <Boton variante="secundario" className="w-full" cargando={abriendo} onClick={abrirCuenta}>
              <Icono nombre="mas" className="h-4 w-4" />
              Abrir otra cuenta de ahorros
            </Boton>
          )}
          {detalle ? <ResumenMes movimientos={detalle.movimientos} /> : <Silueta className="h-32 rounded-3xl" />}
          {lista.length > 0 && <EnvioRapido cuentas={lista} origen={seleccionada} />}
        </div>

        {/* ------------------------------ Columna derecha */}
        <div className="min-w-0 space-y-6">
          {seleccionada && <GraficaMeses cuenta={seleccionada} />}

          <Tarjeta className="p-0">
            <div className="border-b border-marca-100 px-6 py-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-marca-700">Movimientos</h2>
                  {detalle && (
                    <p className="text-sm text-slate-500">
                      Cuenta {enmascarar(detalle.cuenta)}, {conFiltro ? 'según las fechas elegidas' : 'últimos 50'}
                    </p>
                  )}
                </div>
                <Boton variante="secundario" disabled={!detalle?.movimientos.length} onClick={() => descargarExtracto(detalle)}>
                  <Icono nombre="descargar" className="h-4 w-4" />
                  Descargar extracto
                </Boton>
              </div>
              {/* Filtro por fechas */}
              <div className="mt-4 flex flex-wrap items-end gap-3">
                <CampoFecha etiqueta="Desde" value={filtro.desde} max={filtro.hasta || undefined}
                            onChange={(e) => setFiltro({ ...filtro, desde: e.target.value })} />
                <CampoFecha etiqueta="Hasta" value={filtro.hasta} min={filtro.desde || undefined}
                            onChange={(e) => setFiltro({ ...filtro, hasta: e.target.value })} />
                {conFiltro && (
                  <button onClick={() => setFiltro({ desde: '', hasta: '' })} className="enlace-vivo mb-2 text-sm font-medium text-marca-700">
                    Quitar filtro
                  </button>
                )}
              </div>
            </div>
            {!detalle ? (
              <Cargando texto="Cargando movimientos" />
            ) : detalle.movimientos.length === 0 ? (
              conFiltro ? (
                <EstadoVacio icono="calendario" titulo="Sin movimientos en esas fechas">
                  Prueba con un rango más amplio o quita el filtro.
                </EstadoVacio>
              ) : (
                <EstadoVacio icono="enviar" titulo="Aún no tienes movimientos">
                  Cuando recibas o envíes dinero, lo verás aquí. Para tu primer depósito, acércate a una oficina.
                </EstadoVacio>
              )
            ) : (
              <TablaMovimientos movimientos={detalle.movimientos} />
            )}
          </Tarjeta>
        </div>
      </div>

      {cerrando && (
        <DialogoCerrarCuenta
          cuenta={cerrando}
          otras={activas.filter((c) => c.numero !== cerrando.numero)}
          onCerrar={() => setCerrando(null)}
          onListo={() => {
            setCerrando(null)
            cargarCuentas()
          }}
        />
      )}
    </div>
  )
}

// Tarjeta de una cuenta: se inclina siguiendo el mouse, con un reflejo de luz.
// Desde aqui se copia el numero de cuenta y se puede cerrar la cuenta.
function TarjetaCuenta({ c, activa, onClick, puedeCerrar, onCerrar }) {
  const avisar = useAviso()
  const apartado = Number(c.apartado || 0)

  function inclinar(e) {
    const caja = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - caja.left) / caja.width // 0 a 1
    const y = (e.clientY - caja.top) / caja.height
    e.currentTarget.style.setProperty('--ry', `${(x - 0.5) * 10}deg`)
    e.currentTarget.style.setProperty('--rx', `${(0.5 - y) * 10}deg`)
    e.currentTarget.style.setProperty('--bx', `${x * 100}%`)
    e.currentTarget.style.setProperty('--by', `${y * 100}%`)
  }
  function soltar(e) {
    e.currentTarget.style.setProperty('--rx', '0deg')
    e.currentTarget.style.setProperty('--ry', '0deg')
  }

  async function copiar(e) {
    e.stopPropagation() // no seleccionar la tarjeta al copiar
    if (await copiarTexto(c.numero)) {
      avisar(`Número de cuenta ${enmascarar(c.numero)} copiado`)
    } else {
      avisar('No se pudo copiar. Tu número de cuenta es ' + c.numero, 'error')
    }
  }

  return (
    // Es un div (no un <button>) porque adentro tiene otros botones
    <div
      role="button"
      tabIndex={0}
      aria-pressed={activa}
      onClick={onClick}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget && (e.preventDefault(), onClick())}
      onMouseMove={inclinar}
      onMouseLeave={soltar}
      className={`tarjeta-inclinable relative cursor-pointer overflow-hidden rounded-3xl p-6 text-white shadow-lg ${
        activa
          ? 'bg-gradient-to-br from-marca-500 to-marca-800 shadow-marca-900/30 ring-4 ring-marca-200'
          : 'bg-gradient-to-br from-slate-500 to-slate-700 opacity-80 hover:opacity-100'
      }`}
    >
      <span className="tarjeta-reflejo pointer-events-none absolute inset-0" />
      <div className="relative">
        <div className="flex items-center justify-between gap-3 text-sm text-white/80">
          <span>Cuenta de {c.tipo}</span>
          <button onClick={copiar} className="flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 hover:bg-white/20"
                  title="Copiar número de cuenta" aria-label={`Copiar número de cuenta ${enmascarar(c.numero)}`}>
            <span className="cifras">{enmascarar(c.numero)}</span>
            <Icono nombre="copiar" className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="mt-7 text-xs text-white/70">{apartado > 0 ? 'Saldo de la cuenta' : 'Saldo disponible'}</div>
        <div className="font-titulo text-3xl font-bold tracking-tight"><Dinero valor={c.saldo} /></div>
        {apartado > 0 && (
          <div className="mt-2 text-xs text-white/80">
            Disponible <Dinero valor={Math.max(0, Number(c.saldo) - apartado)} animado={false} /> · En metas{' '}
            <Dinero valor={apartado} animado={false} />
          </div>
        )}
        <div className="mt-4 flex items-center justify-between gap-3">
          {c.estado !== 'activa' ? (
            <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">Cuenta {c.estado}</span>
          ) : <span />}
          {puedeCerrar && (
            <button onClick={(e) => { e.stopPropagation(); onCerrar() }} className="text-xs font-medium text-white/75 hover:text-white">
              Cerrar cuenta
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Copia un texto al portapapeles. Si el navegador no deja usar la forma moderna
// (por ejemplo, fuera de HTTPS), usa la forma clasica con un campo oculto.
async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    const campo = document.createElement('textarea')
    campo.value = texto
    campo.setAttribute('readonly', '')
    campo.style.position = 'fixed'
    campo.style.opacity = '0'
    document.body.appendChild(campo)
    campo.select()
    let copiado = false
    try {
      copiado = document.execCommand('copy')
    } catch {}
    campo.remove()
    return copiado
  }
}

// Confirmar el cierre de una cuenta. Si tiene saldo, se elige a donde pasarlo.
function DialogoCerrarCuenta({ cuenta, otras, onCerrar, onListo }) {
  const avisar = useAviso()
  const tieneSaldo = Number(cuenta.saldo) > 0
  const [password, setPassword] = useState('')
  const [destino, setDestino] = useState(otras[0]?.numero ?? '')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function cerrar(e) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const r = await api.post(`/cuentas/${cuenta.numero}/cerrar`, { password, destino: tieneSaldo ? destino : null })
      avisar(Number(r.saldo_trasladado) > 0
        ? `Cuenta ${enmascarar(cuenta.numero)} cerrada. Pasamos ${cop(r.saldo_trasladado)} a ${enmascarar(destino)}`
        : `Cuenta ${enmascarar(cuenta.numero)} cerrada`)
      onListo()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialogo titulo={`Cerrar la cuenta ${enmascarar(cuenta.numero)}`} onCerrar={onCerrar}>
      <form onSubmit={cerrar} className="space-y-4">
        <ul className="space-y-1.5 text-sm text-slate-600">
          <li>· La cuenta deja de aparecer y no se puede volver a abrir.</li>
          <li>· Sus llaves se desactivan y sus metas de ahorro se eliminan.</li>
          <li>· Tus movimientos se conservan en el historial del banco.</li>
        </ul>
        {tieneSaldo && (
          <Selector
            etiqueta={`Pasar el saldo (${cop(cuenta.saldo)}) a`}
            value={destino}
            onChange={(e) => setDestino(e.target.value)}
            opciones={otras.map((c) => ({ valor: c.numero, texto: `Ahorros ${enmascarar(c.numero)}` }))}
          />
        )}
        <Campo etiqueta="Tu contraseña, para confirmar" type="password" required autoComplete="current-password" autoFocus
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-3 pt-1">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" variante="peligro" cargando={enviando}>Cerrar cuenta</Boton>
        </div>
      </form>
    </Dialogo>
  )
}

// Entradas contra salidas de los ultimos 6 meses (solo lo que si se aplico)
function GraficaMeses({ cuenta }) {
  const [datos, setDatos] = useState(null)
  const { oculto } = useSaldoOculto()

  useEffect(() => {
    setDatos(null)
    const hoy = new Date()
    const meses = []
    for (let i = 5; i >= 0; i--) {
      const f = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1)
      meses.push({ clave: `${f.getFullYear()}-${f.getMonth()}`, mes: f.toLocaleString('es-CO', { month: 'short' }).replace('.', ''), entradas: 0, salidas: 0 })
    }
    const desde = new Date(hoy.getFullYear(), hoy.getMonth() - 5, 1).toISOString().slice(0, 10)
    api.get(`/cuentas/${cuenta}/movimientos?desde=${desde}&limite=500`).then((r) => {
      for (const m of r.movimientos) {
        if (m.estado !== 'aprobada') continue
        const f = new Date(m.fecha)
        const fila = meses.find((x) => x.clave === `${f.getFullYear()}-${f.getMonth()}`)
        if (fila) fila[m.sentido === 'entrada' ? 'entradas' : 'salidas'] += Number(m.monto)
      }
      setDatos(meses)
    }).catch(() => setDatos([]))
  }, [cuenta])

  const vacia = datos && datos.every((m) => m.entradas === 0 && m.salidas === 0)

  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-marca-700">Tus últimos 6 meses</h2>
        <div className="flex gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-marca-500" />Entradas</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-oro" />Salidas</span>
        </div>
      </div>
      {!datos ? (
        <Silueta className="h-52 rounded-2xl" />
      ) : vacia ? (
        <p className="py-14 text-center text-sm text-slate-500">Cuando tengas movimientos, aquí verás cuánto entra y sale cada mes.</p>
      ) : (
        <ResponsiveContainer width="100%" height={210}>
          <BarChart data={datos} barGap={4}>
            <CartesianGrid vertical={false} stroke="#DAE4D7" />
            <XAxis dataKey="mes" stroke="#627868" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#627868" fontSize={11} tickLine={false} axisLine={false} width={oculto ? 10 : 60}
                   tickFormatter={(v) => (oculto ? '' : v >= 1e6 ? `${(v / 1e6).toLocaleString('es-CO')} M` : `${Math.round(v / 1000)} mil`)} />
            <Tooltip
              cursor={{ fill: '#F4F9F1' }}
              formatter={(v, nombre) => [oculto ? '$ ••••••' : cop(v), nombre === 'entradas' ? 'Entradas' : 'Salidas']}
              contentStyle={{ borderRadius: 12, border: '1px solid #CDE4C4', fontSize: 12 }}
            />
            <Bar dataKey="entradas" fill="#4D774E" radius={[6, 6, 0, 0]} maxBarSize={28} />
            <Bar dataKey="salidas" fill="#F1B24A" radius={[6, 6, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Tarjeta>
  )
}

// Campo de fecha pequeno para el filtro del extracto
function CampoFecha({ etiqueta, ...resto }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{etiqueta}</span>
      <input type="date" className="rounded-xl border-0 bg-white px-3 py-2 text-sm text-marca-900 ring-1 ring-marca-200 hover:ring-marca-300 focus:outline-none focus:ring-2 focus:ring-marca-500" {...resto} />
    </label>
  )
}

// El mensaje de una transferencia lo escribe OTRA persona. Si empieza por
// = + - @, Excel lo ejecutaria como formula ("inyeccion CSV"); con un
// apostrofo delante, Excel lo muestra como texto.
function textoSeguro(valor) {
  if (!valor) return ''
  return /^[=+\-@\t\r]/.test(valor) ? `'${valor}` : valor
}

// Descarga los movimientos que estan en pantalla como archivo CSV (se abre en Excel)
function descargarExtracto(detalle) {
  const filas = [['Fecha', 'Tipo', 'Sentido', 'Contraparte', 'Mensaje', 'Estado', 'Valor']]
  for (const m of detalle.movimientos) {
    filas.push([fechaHora(m.fecha), TIPOS[m.tipo], m.sentido, m.contraparte ?? '', textoSeguro(m.mensaje), ESTADOS[m.estado].texto,
                (m.sentido === 'entrada' ? '' : '-') + Number(m.monto)])
  }
  // Punto y coma como separador (el Excel en espanol lo espera) y comillas por si hay comas
  const texto = filas.map((f) => f.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(';')).join('\r\n')
  // El primer caracter (BOM) le dice a Excel que el archivo esta en UTF-8 (tildes)
  const archivo = new Blob(['\uFEFF' + texto], { type: 'text/csv;charset=utf-8' })
  const enlace = document.createElement('a')
  enlace.href = URL.createObjectURL(archivo)
  enlace.download = `extracto-${detalle.cuenta.slice(-4)}.csv`
  enlace.click()
  URL.revokeObjectURL(enlace.href)
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
      <h2 className="text-lg font-semibold text-marca-700">Este mes <span className="font-normal capitalize text-slate-500">({mes})</span></h2>
      <div className="flex justify-between text-sm">
        <span className="flex items-center gap-1.5 text-slate-500"><Icono nombre="entrada" className="h-4 w-4" /> Entradas</span>
        <span className="font-semibold text-marca-600">+<Dinero valor={entradas} animado={false} /></span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="flex items-center gap-1.5 text-slate-500"><Icono nombre="salida" className="h-4 w-4" /> Salidas</span>
        <span className="font-semibold">−<Dinero valor={salidas} animado={false} /></span>
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
      <h2 className="mb-3 text-lg font-semibold text-marca-700">Envío rápido</h2>
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
    <div className="sin-barras overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-6 py-3 font-medium">Fecha</th>
            <th className="py-3 font-medium">Descripción</th>
            <th className="py-3 font-medium">Estado</th>
            <th className="px-6 py-3 text-right font-medium">Valor</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {movimientos.map((m) => {
            const entrada = m.sentido === 'entrada'
            const estado = ESTADOS[m.estado]
            const noAplicada = m.estado !== 'aprobada' // retenida/bloqueada: el dinero no se movio
            return (
              <tr key={m.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-6 py-3 text-slate-500">{fechaHora(m.fecha)}</td>
                <td className="py-3">
                  <div className="flex items-center gap-3">
                    <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${
                      entrada ? 'bg-marca-50 text-marca-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      <Icono nombre={entrada ? 'entrada' : 'salida'} className="h-4 w-4" />
                    </span>
                    <span className="font-medium">
                      {TIPOS[m.tipo]}{' '}
                      {m.contraparte && <span className="font-normal text-slate-500">{entrada ? 'de' : 'a'} {m.contraparte}</span>}
                      {m.mensaje && <span className="block max-w-xs truncate text-xs font-normal italic text-marca-600" title={m.mensaje}>“{m.mensaje}”</span>}
                    </span>
                  </div>
                </td>
                <td className="py-3"><Insignia color={estado.color}>{estado.texto}</Insignia></td>
                <td className={`cifras whitespace-nowrap px-6 py-3 text-right font-semibold ${
                  noAplicada ? 'text-slate-400 line-through' : entrada ? 'text-marca-600' : ''
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
