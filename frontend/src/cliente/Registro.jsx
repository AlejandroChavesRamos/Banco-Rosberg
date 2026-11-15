// Registro en linea: abre una cuenta de ahorros en Banco Rosberg
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Logo } from '../componentes/ui'
import { enmascarar } from '../formato'
import MarcoPublico from './MarcoPublico'

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
      <MarcoPublico>
        <div className="text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-marca-100 text-3xl text-marca-700 dark:bg-marca-950 dark:text-marca-300">
            ✓
          </div>
          <h1 className="text-3xl font-bold">¡Bienvenido a Rosberg!</h1>
          <p className="mt-2 text-slate-500">Tu cuenta de ahorros {enmascarar(cuentaCreada)} está lista.</p>
          <Link to="/app/login" className="mt-8 inline-block w-full rounded-xl bg-marca-600 px-4 py-3 text-sm font-semibold text-white">
            Iniciar sesión
          </Link>
        </div>
      </MarcoPublico>
    )
  }

  return (
    <MarcoPublico>
      <div className="mb-8 lg:hidden">
        <Logo subtitulo="Banco Rosberg" />
      </div>
      <h1 className="text-3xl font-bold tracking-tight">Abre tu cuenta</h1>
      <p className="mb-8 mt-1 text-slate-500">Sin cuota de manejo y en menos de un minuto.</p>
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
      <p className="mt-8 text-sm text-slate-500">
        ¿Ya tienes cuenta? <Link to="/app/login" className="font-semibold text-marca-600">Ingresa</Link>
      </p>
    </MarcoPublico>
  )
}
