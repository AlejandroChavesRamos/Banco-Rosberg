// Marco de las pantallas publicas (login y registro):
// barra superior fija, portada con foto a la izquierda y formulario a la derecha.
// "secciones" es lo que aparece al bajar (tarjeta, preguntas, contacto); solo lo usa el login.
import { Link, NavLink } from 'react-router-dom'
import IntroLogo from '../componentes/IntroLogo'
import { Logo } from '../componentes/ui'
import fotoPortada from '../imagenes/portada.jpg'

// Los tres primeros llevan a secciones de la pantalla de login; el ultimo es una pagina aparte
const ENLACES = [
  ['/app/login#tarjeta', 'Tarjeta'],
  ['/app/login#preguntas', 'Preguntas'],
  ['/app/login#contacto', 'Contacto'],
  ['/app/carreras', 'Trabaja con nosotros'],
]

// Barra superior fija de todas las paginas publicas
export function BarraPublica({ accion = 'registro' }) {
  return (
    <header className="sticky top-0 z-20 border-b border-marca-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-3">
        <Link to="/app/login" aria-label="Banco Rosberg, inicio">
          <Logo />
        </Link>
        <nav className="hidden gap-7 text-sm font-medium text-marca-700 md:flex">
          {ENLACES.map(([a, texto]) => (
            <NavLink key={a} to={a} end className={({ isActive }) => `enlace-vivo ${isActive && !a.includes('#') ? 'font-semibold' : ''}`}>
              {texto}
            </NavLink>
          ))}
        </nav>
        <Link
          to={accion === 'registro' ? '/app/registro' : '/app/login'}
          className="boton-vivo ml-auto rounded-full bg-oro px-5 py-2 text-sm font-semibold text-marca-900 hover:bg-oro-claro"
        >
          {accion === 'registro' ? 'Abrir cuenta' : 'Ingresar'}
        </Link>
      </div>
    </header>
  )
}

export default function MarcoPublico({ children, secciones, accion = 'registro' }) {
  return (
    <div className="min-h-screen bg-white">
      <IntroLogo />
      <BarraPublica accion={accion} />

      <main>
        <section className="mx-auto grid max-w-6xl gap-10 px-6 py-8 lg:grid-cols-[1.15fr_1fr] lg:gap-16 lg:py-12">
          {/* Foto con el mensaje del banco (se oculta en pantallas angostas) */}
          <div className="relative hidden min-h-[36rem] overflow-hidden rounded-[2rem] bg-marca-700 lg:block">
            <img src={fotoPortada} alt="Clienta sonriendo mientras usa su celular" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-marca-900 via-marca-900/35 to-transparent" />
            <span className="absolute left-8 top-8 rounded-full bg-oro px-4 py-1.5 text-sm font-semibold text-marca-900">
              Sin cuota de manejo
            </span>
            <div className="absolute inset-x-0 bottom-0 p-10 text-white">
              <p className="font-titulo text-5xl font-bold leading-[1.05] tracking-tight">
                Tu banco, sin filas y sin sorpresas.
              </p>
              <p className="mt-4 max-w-sm text-lg text-white/85">
                Maneja tu dinero desde el computador, con cada operación vigilada contra el fraude.
              </p>
            </div>
          </div>

          <div className="mx-auto flex w-full max-w-md flex-col justify-center py-6">{children}</div>
        </section>

        {secciones}
      </main>
    </div>
  )
}
