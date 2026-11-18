// Registro en linea: abre una cuenta de ahorros en Banco Rosberg
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Logo, Volver } from '../componentes/ui'
import { enmascarar } from '../formato'
import IntroLogo from '../componentes/IntroLogo'
import fotoFondo from '../imagenes/registro.jpg'

export default function Registro() {
  // Un solo objeto con todos los campos del formulario
  const [datos, setDatos] = useState({ nombre: '', email: '', cedula: '', celular: '', password: '', confirmar: '' })
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [cuentaCreada, setCuentaCreada] = useState(null)

  // Actualiza un campo sin perder los demas
  function cambiar(campo) {
    return (e) => setDatos({ ...datos, [campo]: e.target.value })
  }

  async function registrar(evento) {
    evento.preventDefault()
    setError('')
    if (datos.password !== datos.confirmar) {
      setError('Las contraseñas no coinciden')
      return
    }
    setEnviando(true)
    try {
      const { confirmar, ...cuerpo } = datos
      const r = await api.post('/auth/registro', cuerpo, { sinRenovar: true })
      setCuentaCreada(r.cuenta)
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  if (cuentaCreada) {
    return (
      <MarcoRegistro>
        <div className="text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center confirmado rounded-full bg-marca-100 text-3xl text-marca-700">
            ✓
          </div>
          <h1 className="font-titulo text-4xl font-bold tracking-tight text-marca-700">¡Bienvenido a Rosberg!</h1>
          <p className="mt-2 text-marca-500">Tu cuenta de ahorros {enmascarar(cuentaCreada)} está lista.</p>
          <Link to="/app/login" className="boton-vivo boton-sombra mt-8 inline-block w-full rounded-xl bg-marca-700 px-4 py-3 text-sm font-semibold text-white hover:bg-marca-800">
            Iniciar sesión
          </Link>
        </div>
      </MarcoRegistro>
    )
  }

  return (
    <MarcoRegistro>
      <h1 className="mb-7 font-titulo text-2xl font-semibold leading-snug tracking-tight text-marca-800">
        Abre tu <span className="text-marca-500">cuenta de ahorros sin cuota de manejo</span> en menos de un minuto
      </h1>
      <form onSubmit={registrar} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Campo etiqueta="Nombre completo" required value={datos.nombre} onChange={cambiar('nombre')} />
        </div>
        <div className="sm:col-span-2">
          <Campo etiqueta="Correo" type="email" required value={datos.email} onChange={cambiar('email')} />
        </div>
        <Campo etiqueta="Cédula" inputMode="numeric" required pattern="\d{6,10}" title="Entre 6 y 10 dígitos"
               value={datos.cedula} onChange={cambiar('cedula')} />
        <Campo etiqueta="Celular" inputMode="numeric" required pattern="3\d{9}" title="10 dígitos, empieza por 3"
               placeholder="3001234567" value={datos.celular} onChange={cambiar('celular')} />
        <Campo etiqueta="Contraseña" type="password" required minLength={10} autoComplete="new-password"
               ayuda="Mín. 10 caracteres, letras y números" value={datos.password} onChange={cambiar('password')} />
        <Campo etiqueta="Repite la contraseña" type="password" required autoComplete="new-password"
               value={datos.confirmar} onChange={cambiar('confirmar')} />
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="sm:col-span-2">
          <Boton type="submit" cargando={enviando} className="w-full py-3">Crear mi cuenta</Boton>
        </div>
      </form>
      <p className="mt-6 text-sm text-marca-500">
        ¿Ya tienes cuenta? <Link to="/app/login" className="enlace-vivo font-semibold text-marca-700">Ingresa</Link>
      </p>
    </MarcoRegistro>
  )
}

// ---------------------------------------------------------------------
// Marco de esta pantalla: foto de fondo, a la izquierda lo que ofrece la
// cuenta y a la derecha la caja blanca con el formulario.
// ---------------------------------------------------------------------
const VENTAJAS = [
  ['$0', 'Sin cuota de manejo', 'Abrir y tener la cuenta no cuesta nada.'],
  ['llave', 'Envía con llaves', 'Transfiere a un celular o a un correo, sin pedir números de cuenta.'],
  ['codigo', 'Retira con un código', 'Genera un código en la app y retira tu dinero en la oficina.'],
  ['escudo', 'Protección antifraude', 'Revisamos cada operación en tiempo real para cuidar tu dinero.'],
]

const TRAZOS = {
  llave: <><circle cx="8" cy="15" r="4" /><path d="M11 12l8-8M16 7l3 3M14 9l2 2" /></>,
  codigo: <><rect x="4" y="5" width="16" height="14" rx="3" /><path d="M8 10v4M12 10v4M16 10v4" /></>,
  escudo: <><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /><path d="M9 12l2.2 2.2L15.5 10" /></>,
}

function MarcoRegistro({ children }) {
  return (
    <div className="relative min-h-screen bg-marca-900">
      <IntroLogo />
      {/* Foto de fondo, oscurecida para que el texto se lea */}
      <img src={fotoFondo} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-r from-marca-950/85 via-marca-950/35 to-marca-950/60" />

      <div className="relative">
        <header className="bg-white">
          <div className="mx-auto grid max-w-6xl grid-cols-3 items-center px-6 py-3">
            <Volver a="/app/login" className="justify-self-start" />
            <Link to="/app/login" className="justify-self-center" aria-label="Banco Rosberg, inicio">
              <Logo />
            </Link>
            <Link to="/app/login" className="boton-vivo boton-sombra justify-self-end rounded-full bg-oro px-5 py-2 text-sm font-semibold text-marca-900 hover:bg-oro-claro">
              Ingresar
            </Link>
          </div>
        </header>

        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[1fr_27rem] lg:py-14">
          <div className="hidden max-w-sm self-center text-white lg:block">
            <p className="font-titulo text-4xl font-semibold leading-tight tracking-tight">
              Una cuenta de ahorros para manejar tu dinero sin filas
            </p>
            <ul className="mt-10 space-y-7">
              {VENTAJAS.map(([icono, titulo, texto]) => (
                <li key={titulo} className="flex gap-4">
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-oro font-titulo text-lg font-bold text-marca-900">
                    {TRAZOS[icono] ? (
                      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        {TRAZOS[icono]}
                      </svg>
                    ) : icono}
                  </span>
                  <div>
                    <div className="font-semibold">{titulo}</div>
                    <div className="mt-0.5 text-sm leading-relaxed text-white/85">{texto}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-3xl bg-white p-7 shadow-2xl shadow-marca-950/50 sm:p-9">{children}</div>
        </div>

        <p className="mx-auto max-w-6xl px-6 pb-8 text-xs text-white/70">
          Banco Rosberg es un proyecto académico: no es una entidad financiera real ni maneja dinero real.
        </p>
      </div>
    </div>
  )
}
