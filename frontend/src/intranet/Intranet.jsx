// =====================================================================
// Intranet Rosberg (empleados): rutas, menu lateral segun el rol y login.
// =====================================================================
import { useState } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import CambiarClave from '../cliente/CambiarClave'
import { ConfigurarDosPasos, PasoCodigo } from '../componentes/DosPasos'
import { Aviso, Boton, BotonTema, Campo, Logo, PantallaCargando, Tarjeta } from '../componentes/ui'
import { useSesion } from '../sesion'
import Alertas from './Alertas'
import Auditoria from './Auditoria'
import Empleados from './Empleados'
import Investigar from './Investigar'
import Reglas from './Reglas'
import Tablero from './Tablero'
import Ventanilla from './Ventanilla'

// Que ve cada rol en el menu (el backend igual valida cada operacion)
const MENU = [
  { a: '/intranet/tablero', texto: 'Tablero', icono: '▦', roles: ['analista', 'admin'] },
  { a: '/intranet/alertas', texto: 'Alertas', icono: '⚠', roles: ['analista', 'admin'] },
  { a: '/intranet/investigar', texto: 'Investigar cuenta', icono: '⌕', roles: ['analista', 'admin'] },
  { a: '/intranet/ventanilla', texto: 'Ventanilla', icono: '⎘', roles: ['cajero', 'admin'] },
  { a: '/intranet/empleados', texto: 'Empleados', icono: '☺', roles: ['admin'] },
  { a: '/intranet/reglas', texto: 'Reglas antifraude', icono: '⚙', roles: ['admin'] },
  { a: '/intranet/auditoria', texto: 'Auditoría', icono: '⛓', roles: ['admin'] },
  { a: '/intranet/seguridad', texto: 'Mi seguridad', icono: '🔒', roles: ['cajero', 'analista', 'admin'] },
]

const NOMBRE_ROL = { cajero: 'Cajero', analista: 'Analista de fraude', admin: 'Administrador' }

export default function Intranet() {
  return (
    <Routes>
      <Route path="login" element={<LoginIntranet />} />
      <Route element={<Marco />}>
        <Route index element={<Inicio />} />
        <Route path="tablero" element={<Tablero />} />
        <Route path="alertas" element={<Alertas />} />
        <Route path="investigar" element={<Investigar />} />
        <Route path="investigar/:numero" element={<Investigar />} />
        <Route path="ventanilla" element={<Ventanilla />} />
        <Route path="empleados" element={<Empleados />} />
        <Route path="reglas" element={<Reglas />} />
        <Route path="auditoria" element={<Auditoria />} />
        <Route path="cambiar-clave" element={<div className="max-w-md"><CambiarClave /></div>} />
        <Route
          path="seguridad"
          element={
            <div className="max-w-2xl space-y-6">
              <h1 className="text-2xl font-bold tracking-tight">Mi seguridad</h1>
              <ConfigurarDosPasos />
            </div>
          }
        />
      </Route>
    </Routes>
  )
}

// Al entrar, cada rol cae en su pantalla principal
function Inicio() {
  const { usuario } = useSesion()
  return <Navigate to={usuario.rol === 'cajero' ? '/intranet/ventanilla' : '/intranet/tablero'} replace />
}

function Marco() {
  const { usuario, cargando, cerrarSesion } = useSesion()
  const ubicacion = useLocation()
  const navegar = useNavigate()

  if (cargando) return <PantallaCargando />
  if (!usuario) return <Navigate to="/intranet/login" replace />
  if (usuario.debeCambiar && ubicacion.pathname !== '/intranet/cambiar-clave') {
    return <Navigate to="/intranet/cambiar-clave" replace />
  }
  // El admin exige 2FA a empleados y este aun no lo configura
  if (!usuario.debeCambiar && usuario.debeConfigurar2fa && ubicacion.pathname !== '/intranet/seguridad') {
    return <Navigate to="/intranet/seguridad" replace />
  }

  async function salir() {
    await cerrarSesion()
    navegar('/intranet/login')
  }

  const bloqueado = usuario.debeCambiar || usuario.debeConfigurar2fa
  const opciones = MENU.filter((m) => m.roles.includes(usuario.rol))

  return (
    <div className="flex min-h-screen">
      {/* Menu lateral */}
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-5 dark:border-slate-800 dark:bg-slate-900">
        <div className="px-2">
          <Logo subtitulo="Intranet" />
        </div>
        <nav className="mt-8 flex-1 space-y-1">
          {!bloqueado &&
            opciones.map((m) => (
              <NavLink
                key={m.a}
                to={m.a}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium ${
                    isActive
                      ? 'bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                  }`
                }
              >
                <span className="w-5 text-center">{m.icono}</span>
                {m.texto}
              </NavLink>
            ))}
        </nav>
        <div className="border-t border-slate-200 px-2 pt-4 dark:border-slate-800">
          <div className="truncate text-sm font-semibold">{usuario.nombre}</div>
          <div className="text-xs text-slate-500">{NOMBRE_ROL[usuario.rol]}</div>
          <div className="mt-3 flex items-center justify-between">
            <BotonTema />
            <button onClick={salir} className="text-sm font-medium text-slate-500 hover:text-red-600">
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido de la pantalla actual */}
      <main className="min-w-0 flex-1 p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  )
}

function LoginIntranet() {
  const { usuario, cargando, iniciarSesion } = useSesion()
  const navegar = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [token2fa, setToken2fa] = useState(null)

  if (cargando) return <PantallaCargando />
  if (usuario) return <Navigate to="/intranet" replace />

  function entrarAlPanel(r) {
    navegar(r.debe_cambiar_password ? '/intranet/cambiar-clave' : '/intranet')
  }

  async function entrar(evento) {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const r = await iniciarSesion(email, password)
      if (r.requiere_2fa) setToken2fa(r.token_2fa)
      else entrarAlPanel(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 p-4 dark:bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <Logo subtitulo="Intranet · uso exclusivo de empleados" />
          <BotonTema />
        </div>
        {token2fa ? (
          <Tarjeta>
            <PasoCodigo token2fa={token2fa} onListo={entrarAlPanel} onCancelar={() => { setToken2fa(null); setPassword('') }} />
          </Tarjeta>
        ) : (
        <Tarjeta>
          <form onSubmit={entrar} className="space-y-4">
            <Campo etiqueta="Correo corporativo" type="email" required autoComplete="username"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <Campo etiqueta="Contraseña" type="password" required autoComplete="current-password"
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            <Aviso>{error}</Aviso>
            <Boton type="submit" cargando={enviando} className="w-full">Ingresar</Boton>
          </form>
        </Tarjeta>
        )}
        <p className="mt-4 text-center text-xs text-slate-500">
          Toda actividad en la Intranet queda registrada en la auditoría.
        </p>
      </div>
    </div>
  )
}
