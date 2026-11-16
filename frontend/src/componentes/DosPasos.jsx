// =====================================================================
// Piezas de la verificacion en dos pasos (2FA), usadas en los dos portales:
//   <PasoCodigo>       el segundo paso del login (escribir el codigo)
//   <ConfigurarDosPasos> activar/desactivar con codigo QR
// =====================================================================
import { useEffect, useState } from 'react'
import { api } from '../api'
import { useSesion } from '../sesion'
import { Aviso, Boton, Campo, Girando, Tarjeta } from './ui'

// Campo para un codigo de 6 digitos
export function CampoCodigo({ valor, onCambio, autoFocus }) {
  return (
    <input
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      autoFocus={autoFocus}
      required
      pattern="\d{6}"
      placeholder="000000"
      value={valor}
      onChange={(e) => onCambio(e.target.value.replace(/\D/g, ''))}
      className="cifras w-full rounded-xl border-0 bg-white px-4 py-3 text-center text-2xl font-bold tracking-[0.5em] ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-marca-500 dark:bg-slate-900 dark:ring-slate-700"
    />
  )
}

// Segundo paso del login
export function PasoCodigo({ token2fa, onListo, onCancelar }) {
  const { verificarCodigo } = useSesion()
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function verificar(e) {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      onListo(await verificarCodigo(token2fa, codigo))
    } catch (err) {
      setError(err.message)
      setCodigo('')
    } finally {
      setCargando(false)
    }
  }

  return (
    <form onSubmit={verificar} className="space-y-5">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-marca-50 text-2xl text-marca-700 dark:bg-marca-950 dark:text-marca-300">🔒</div>
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Verificación en dos pasos</h2>
        <p className="mt-1 text-sm text-slate-500">Abre tu app autenticadora (Google Authenticator) y escribe el código de 6 dígitos.</p>
      </div>
      <CampoCodigo valor={codigo} onCambio={setCodigo} autoFocus />
      <Aviso>{error}</Aviso>
      <Boton type="submit" cargando={cargando} className="w-full py-3" disabled={codigo.length !== 6}>Verificar</Boton>
      <button type="button" onClick={onCancelar} className="w-full text-sm text-slate-500 hover:text-slate-700">
        Volver
      </button>
    </form>
  )
}

// Activar / desactivar el 2FA con codigo QR
export function ConfigurarDosPasos() {
  const { usuario, marcar2faActivo } = useSesion()
  const [estado, setEstado] = useState(null)
  const [qr, setQr] = useState(null) // { qr_svg, secreto } mientras se configura
  const [codigo, setCodigo] = useState('')
  const [password, setPassword] = useState('')
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' })
  const [cargando, setCargando] = useState(false)

  function cargarEstado() {
    api.get('/auth/2fa/estado').then(setEstado).catch((e) => setMensaje({ tipo: 'error', texto: e.message }))
  }
  useEffect(cargarEstado, [])

  async function accion(funcion) {
    setMensaje({ tipo: '', texto: '' })
    setCargando(true)
    try {
      await funcion()
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e.message })
    } finally {
      setCargando(false)
    }
  }

  const iniciar = () => accion(async () => setQr(await api.post('/auth/2fa/iniciar')))

  const confirmar = (e) => {
    e.preventDefault()
    accion(async () => {
      const r = await api.post('/auth/2fa/confirmar', { codigo })
      setQr(null)
      setCodigo('')
      marcar2faActivo()
      setMensaje({ tipo: 'exito', texto: r.mensaje })
      cargarEstado()
    })
  }

  const desactivar = (e) => {
    e.preventDefault()
    accion(async () => {
      const r = await api.post('/auth/2fa/desactivar', { password, codigo })
      setCodigo('')
      setPassword('')
      setMensaje({ tipo: 'exito', texto: r.mensaje })
      cargarEstado()
    })
  }

  if (!estado) return <Tarjeta className="flex justify-center text-marca-600"><Girando /></Tarjeta>

  return (
    <Tarjeta className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Verificación en dos pasos</h2>
          <p className="text-sm text-slate-500">Además de tu contraseña, te pediremos un código que solo tu celular genera.</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
          estado.activo ? 'bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-800'
        }`}>
          {estado.activo ? 'Activa' : 'Inactiva'}
        </span>
      </div>

      {estado.obligatorio && !estado.activo && (
        <Aviso tipo="advertencia">El banco exige la verificación en dos pasos para todos los empleados. Actívala para continuar.</Aviso>
      )}
      {estado.exigido_en_transferencias && (
        <p className="text-sm text-slate-500">
          El banco la exige para transferencias desde ${Number(estado.monto_2fa).toLocaleString('es-CO')}.
        </p>
      )}
      <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>

      {/* Inactiva y aun sin QR */}
      {!estado.activo && !qr && (
        estado.puede_activar ? (
          <Boton onClick={iniciar} cargando={cargando}>Activar</Boton>
        ) : (
          <p className="text-sm text-slate-500">El banco todavía no ha habilitado esta opción para clientes.</p>
        )
      )}

      {/* Configurando: QR + primer codigo */}
      {!estado.activo && qr && (
        <form onSubmit={confirmar} className="grid gap-5 md:grid-cols-[200px_1fr]">
          <div className="rounded-xl bg-white p-2 ring-1 ring-slate-200" dangerouslySetInnerHTML={{ __html: qr.qr_svg }} />
          <div className="space-y-3 text-sm">
            <ol className="list-decimal space-y-1 pl-4 text-slate-600 dark:text-slate-300">
              <li>Instala Google Authenticator (o Microsoft Authenticator) en tu celular.</li>
              <li>Toca “+” y escanea este código.</li>
              <li>Escribe aquí el código de 6 dígitos que aparece.</li>
            </ol>
            <p className="text-xs text-slate-500">
              ¿No puedes escanear? Escribe esta clave: <span className="font-mono">{qr.secreto}</span>
            </p>
            <CampoCodigo valor={codigo} onCambio={setCodigo} autoFocus />
            <Boton type="submit" cargando={cargando} disabled={codigo.length !== 6}>Confirmar y activar</Boton>
          </div>
        </form>
      )}

      {/* Activa: opcion de desactivar (si no es obligatoria) */}
      {estado.activo && !estado.obligatorio && (
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-500">Desactivar verificación en dos pasos</summary>
          <form onSubmit={desactivar} className="mt-3 max-w-sm space-y-3">
            <Campo etiqueta="Tu contraseña" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <CampoCodigo valor={codigo} onCambio={setCodigo} />
            <Boton variante="peligro" type="submit" cargando={cargando} disabled={codigo.length !== 6}>Desactivar</Boton>
          </form>
        </details>
      )}
      {usuario?.rol !== 'cliente' && estado.activo && estado.obligatorio && (
        <p className="text-sm text-slate-500">Para empleados es obligatoria y no se puede desactivar.</p>
      )}
    </Tarjeta>
  )
}
