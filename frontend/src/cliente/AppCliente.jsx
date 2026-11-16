// =====================================================================
// AppCliente.jsx - Rutas de la App Rosberg (clientes) y su marco comun:
// barra superior con el menu (pensada para computador) y proteccion de
// las pantallas que exigen sesion.
// =====================================================================
import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { BotonTema, Logo, PantallaCargando } from '../componentes/ui'
import { useSesion } from '../sesion'
import CambiarClave from './CambiarClave'
import Inicio from './Inicio'
import Llaves from './Llaves'
import Login from './Login'
import Registro from './Registro'
import AvisosSeguridad from './AvisosSeguridad'
import Retiro from './Retiro'
import Seguridad from './Seguridad'
import Transferir from './Transferir'

export default function AppCliente() {
  return (
    <Routes>
      {/* Pantallas publicas */}
      <Route path="login" element={<Login />} />
      <Route path="registro" element={<Registro />} />

      {/* Pantallas que exigen haber iniciado sesion */}
      <Route element={<Marco />}>
        <Route index element={<Inicio />} />
        <Route path="transferir" element={<Transferir />} />
        <Route path="retiro" element={<Retiro />} />
        <Route path="llaves" element={<Llaves />} />
        <Route path="cambiar-clave" element={<CambiarClave />} />
        <Route path="seguridad" element={<Seguridad />} />
      </Route>
    </Routes>
  )
}

const MENU = [
  { a: '/app', texto: 'Inicio' },
  { a: '/app/transferir', texto: 'Enviar dinero' },
  { a: '/app/retiro', texto: 'Retirar sin tarjeta' },
  { a: '/app/llaves', texto: 'Mis llaves' },
  { a: '/app/seguridad', texto: 'Seguridad' },
]

// Marco comun + proteccion: si no hay sesion, manda al login
function Marco() {
  const { usuario, cargando, cerrarSesion } = useSesion()
  const ubicacion = useLocation()
  const navegar = useNavigate()

  if (cargando) return <PantallaCargando />
  if (!usuario) return <Navigate to="/app/login" replace />
  // Clientes creados en ventanilla: deben cambiar la contrasena temporal primero
  if (usuario.debeCambiar && ubicacion.pathname !== '/app/cambiar-clave') {
    return <Navigate to="/app/cambiar-clave" replace />
  }

  async function salir() {
    await cerrarSesion()
    navegar('/app/login')
  }

  return (
    <div className="min-h-screen">
      {/* Barra superior */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-6 py-3">
          <Logo />
          {!usuario.debeCambiar && (
            <nav className="order-3 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
              {MENU.map((m) => (
                <NavLink
                  key={m.a}
                  to={m.a}
                  end
                  className={({ isActive }) =>
                    `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
                      isActive
                        ? 'bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                    }`
                  }
                >
                  {m.texto}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-2">
            <BotonTema />
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-sm font-semibold">{usuario.nombre}</div>
              <NavLink to="/app/cambiar-clave" className="text-xs text-slate-500 hover:text-marca-600">
                Cambiar contraseña
              </NavLink>
            </div>
            <button
              onClick={salir}
              className="ml-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 ring-1 ring-slate-200 hover:bg-slate-100 dark:text-slate-400 dark:ring-slate-700 dark:hover:bg-slate-800"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* <Outlet /> es el "hueco" donde se dibuja la pantalla actual */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        {!usuario.debeCambiar && <AvisosSeguridad />}
        <Outlet />
      </main>
    </div>
  )
}
