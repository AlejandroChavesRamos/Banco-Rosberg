// =====================================================================
// Intranet Rosberg (empleados): rutas, menu lateral segun el rol y login.
// =====================================================================
import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import CambiarClave from '../cliente/CambiarClave'
import { ConfigurarDosPasos, PasoCodigo } from '../componentes/DosPasos'
import Icono from '../componentes/Icono'
import IntroLogo from '../componentes/IntroLogo'
import NoEncontrado from '../componentes/NoEncontrado'
import { usePeriodico } from '../componentes/usePeriodico'
import { Aviso, Boton, Campo, Logo, PantallaCargando, Volver } from '../componentes/ui'
import fotoIntranet from '../imagenes/intranet.jpg'
import { useSesion } from '../sesion'
import Alertas from './Alertas'
import Asistente from './Asistente'
import Atencion from './Atencion'
import Auditoria from './Auditoria'
import Empleados from './Empleados'
import Investigar from './Investigar'
import Reglas from './Reglas'
import Solicitudes from './Solicitudes'
import Tablero from './Tablero'
import Ventanilla from './Ventanilla'

// Que ve cada rol en el menu (el backend igual valida cada operacion)
const MENU = [
  { a: '/intranet/tablero', texto: 'Tablero', icono: 'tablero', roles: ['analista', 'admin'] },
  { a: '/intranet/alertas', texto: 'Alertas', icono: 'alerta', roles: ['analista', 'admin'] },
  { a: '/intranet/investigar', texto: 'Investigar cuenta', icono: 'lupa', roles: ['analista', 'admin'] },
  { a: '/intranet/ventanilla', texto: 'Ventanilla', icono: 'ventanilla', roles: ['cajero', 'admin'] },
  { a: '/intranet/atencion', texto: 'Atención al cliente', icono: 'chat', roles: ['cajero', 'analista', 'admin'], contador: 'atencion' },
  { a: '/intranet/solicitudes', texto: 'Solicitudes', icono: 'buzon', roles: ['cajero', 'analista', 'admin'], contador: 'solicitudes' },
  { a: '/intranet/asistente', texto: 'Asistente', icono: 'robot', roles: ['admin'] },
  { a: '/intranet/empleados', texto: 'Empleados', icono: 'empleados', roles: ['admin'] },
  { a: '/intranet/reglas', texto: 'Reglas antifraude', icono: 'ajustes', roles: ['admin'] },
  { a: '/intranet/auditoria', texto: 'Auditoría', icono: 'cadena', roles: ['admin'] },
  { a: '/intranet/seguridad', texto: 'Mi seguridad', icono: 'escudo', roles: ['cajero', 'analista', 'admin'] },
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
        <Route path="solicitudes" element={<Solicitudes />} />
        <Route path="atencion" element={<Atencion />} />
        <Route path="asistente" element={<Asistente />} />
        <Route path="cambiar-clave" element={<div className="max-w-md"><CambiarClave /></div>} />
        <Route
          path="seguridad"
          element={
            <div className="max-w-2xl space-y-6">
              <h1 className="font-titulo text-3xl font-bold tracking-tight text-marca-700">Mi seguridad</h1>
              <ConfigurarDosPasos />
            </div>
          }
        />
        <Route path="*" element={<NoEncontrado completa={false} volver="/intranet" textoVolver="Ir al inicio de la Intranet" />} />
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
  // Avisos del menu: clientes esperando asesor + mensajes sin leer de mis
  // tiquetes, y solicitudes de visitantes por responder
  const [contadores, setContadores] = useState({})
  const puedeVerContadores = Boolean(usuario && !usuario.debeCambiar && !usuario.debeConfigurar2fa)
  function cargarContadores() {
    if (!puedeVerContadores) return
    api.get('/atencion/resumen')
      .then((r) => setContadores((c) => ({ ...c, atencion: r.nuevos + r.mios_no_leidos })))
      .catch(() => {})
    api.get('/publico/solicitudes')
      .then((l) => setContadores((c) => ({ ...c, solicitudes: l.length })))
      .catch(() => {})
  }
  usePeriodico(cargarContadores, 15000)
  useEffect(cargarContadores, [puedeVerContadores]) // apenas inicia sesion, sin esperar 15 s

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
      {/* Menu lateral, en el verde del banco */}
      <aside className="no-imprimir sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-marca-700 px-3 py-6 text-white">
        <div className="px-3">
          <Logo claro subtitulo="Intranet" />
        </div>
        <nav className="mt-9 flex-1 space-y-1 overflow-y-auto">
          {!bloqueado &&
            opciones.map((m) => (
              <NavLink
                key={m.a}
                to={m.a}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive ? 'bg-white text-marca-700' : 'text-white/85 hover:bg-white/10 hover:text-white'
                  }`
                }
              >
                <Icono nombre={m.icono} />
                <span className="flex-1">{m.texto}</span>
                {m.contador && contadores[m.contador] > 0 && (
                  <span className="grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-oro px-1.5 text-[11px] font-bold text-marca-900">
                    {contadores[m.contador]}
                  </span>
                )}
              </NavLink>
            ))}
        </nav>
        <div className="border-t border-white/15 px-3 pt-5">
          <div className="truncate text-sm font-semibold">{usuario.nombre}</div>
          <div className="text-xs text-marca-300">{NOMBRE_ROL[usuario.rol]}</div>
          <div className="mt-4 flex flex-col items-start gap-2 text-sm">
            <NavLink to="/intranet/cambiar-clave" className="enlace-vivo text-white/85 hover:text-white">Cambiar contraseña</NavLink>
            <button onClick={salir} className="flex items-center gap-2 font-medium text-oro hover:text-oro-claro">
              <Icono nombre="salir" className="h-4 w-4" />
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido de la pantalla actual */}
      <main className="min-w-0 flex-1 p-6 lg:p-10">
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

  // Mitad imagen, mitad formulario (en pantallas angostas solo el formulario)
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-2">
      <IntroLogo />
      <div className="hidden p-5 lg:block">
        <img src={fotoIntranet} alt="Empleado revisando cifras en un computador portátil"
             className="h-[calc(100vh-2.5rem)] w-full rounded-[2rem] object-cover" />
      </div>
      <div className="flex flex-col justify-center px-6 py-12">
        <div className="mx-auto w-full max-w-sm">
          <Volver a="/app/login" className="mb-10">Volver a la banca en línea</Volver>
          <div>
            <Logo grande subtitulo="Intranet" />
          </div>
          {token2fa ? (
            <div className="mt-12">
              <PasoCodigo token2fa={token2fa} onListo={entrarAlPanel}
                          onCancelar={() => { setToken2fa(null); setPassword('') }} />
            </div>
          ) : (
          <>
          <h1 className="mb-7 mt-12 font-titulo text-3xl font-bold tracking-tight text-marca-700">Ingreso de empleados</h1>
          <form onSubmit={entrar} className="space-y-4">
            <Campo etiqueta="Correo corporativo" type="email" required autoComplete="username"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <Campo etiqueta="Contraseña" type="password" required autoComplete="current-password"
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            <Aviso>{error}</Aviso>
            <Boton type="submit" cargando={enviando} className="w-full py-3">Ingresar</Boton>
          </form>
          <p className="mt-6 text-sm text-marca-600">
            ¿Olvidaste tu contraseña? Pídele a un administrador que te la restablezca.
          </p>
          </>
          )}
          <p className="mt-2 text-xs text-marca-500">
            Toda actividad en la Intranet queda registrada en la auditoría.
          </p>
        </div>
      </div>
    </div>
  )
}
