// =====================================================================
// AppCliente.jsx - Rutas de la App Rosberg (clientes) y su marco comun:
// barra superior con el menu (pensada para computador) y proteccion de
// las pantallas que exigen sesion.
// =====================================================================
import { useEffect, useState } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icono from '../componentes/Icono'
import NoEncontrado from '../componentes/NoEncontrado'
import { usePeriodico } from '../componentes/usePeriodico'
import { Logo, PantallaCargando } from '../componentes/ui'
import { useSesion } from '../sesion'
import Ayuda from './Ayuda'
import CambiarClave from './CambiarClave'
import Carreras from './Carreras'
import Inicio from './Inicio'
import Llaves from './Llaves'
import Login from './Login'
import Perfil from './Perfil'
import Recuperar from './Recuperar'
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
      <Route path="recuperar" element={<Recuperar />} />
      <Route path="carreras" element={<Carreras />} />

      {/* Pantallas que exigen haber iniciado sesion */}
      <Route element={<Marco />}>
        <Route index element={<Inicio />} />
        <Route path="transferir" element={<Transferir />} />
        <Route path="retiro" element={<Retiro />} />
        <Route path="llaves" element={<Llaves />} />
        <Route path="perfil" element={<Perfil />} />
        <Route path="cambiar-clave" element={<CambiarClave />} />
        <Route path="seguridad" element={<Seguridad />} />
        <Route path="ayuda" element={<Ayuda />} />
        <Route path="ayuda/:id" element={<Ayuda />} />
        <Route path="*" element={<NoEncontrado completa={false} volver="/app" textoVolver="Ir a mis cuentas" />} />
      </Route>
    </Routes>
  )
}

const MENU = [
  { a: '/app', texto: 'Inicio', icono: 'inicio' },
  { a: '/app/transferir', texto: 'Enviar dinero', icono: 'enviar' },
  { a: '/app/retiro', texto: 'Retirar sin tarjeta', icono: 'codigo' },
  { a: '/app/llaves', texto: 'Mis llaves', icono: 'llave' },
  { a: '/app/seguridad', texto: 'Seguridad', icono: 'escudo' },
  { a: '/app/ayuda', texto: 'Ayuda', icono: 'chat', contador: true },
]

// Marco comun + proteccion: si no hay sesion, manda al login
function Marco() {
  const { usuario, cargando, cerrarSesion } = useSesion()
  const ubicacion = useLocation()
  const navegar = useNavigate()
  const [sinLeer, setSinLeer] = useState(0) // respuestas del asesor que el cliente no ha visto

  const puedeVer = Boolean(usuario && !usuario.debeCambiar)
  function cargarSinLeer() {
    if (puedeVer) api.get('/ayuda/resumen').then((r) => setSinLeer(r.no_leidos)).catch(() => {})
  }
  usePeriodico(cargarSinLeer, 10000)
  useEffect(cargarSinLeer, [puedeVer]) // apenas inicia sesion, sin esperar 10 s

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
      <header className="no-imprimir sticky top-0 z-10 border-b border-marca-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-6 py-3">
          <Link to="/app" aria-label="Banco Rosberg, inicio">
            <Logo />
          </Link>
          {!usuario.debeCambiar && (
            <nav className="order-3 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
              {MENU.map((m) => (
                <NavLink
                  key={m.a}
                  to={m.a}
                  end={m.a === '/app'}
                  className={({ isActive }) =>
                    `flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                      isActive ? 'bg-marca-700 text-white' : 'text-marca-700 hover:bg-marca-100'
                    }`
                  }
                >
                  <Icono nombre={m.icono} className="h-4 w-4" />
                  {m.texto}
                  {m.contador && sinLeer > 0 && (
                    <span className="grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-oro px-1.5 text-[11px] font-bold text-marca-900"
                          aria-label={`${sinLeer} mensajes sin leer`}>
                      {sinLeer}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3">
            <NavLink
              to="/app/perfil"
              className={({ isActive }) =>
                `hidden items-center gap-2.5 rounded-full py-1 pl-1 pr-4 text-sm font-semibold text-marca-700 transition-colors sm:flex ${
                  isActive ? 'bg-marca-100' : 'hover:bg-marca-50'
                }`
              }
            >
              <span className="grid h-8 w-8 place-items-center rounded-full bg-marca-700 text-white">
                <Icono nombre="usuario" className="h-4 w-4" />
              </span>
              {usuario.nombre.split(' ')[0]}
            </NavLink>
            <button
              onClick={salir}
              className="boton-vivo flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-marca-700 ring-1 ring-marca-200 hover:bg-marca-50"
            >
              <Icono nombre="salir" className="h-4 w-4" />
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
