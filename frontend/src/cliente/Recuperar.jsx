// "Olvide mi contrasena" (solo clientes).
// El banco no envia correos, asi que el cliente demuestra quien es con la
// cedula y el celular que registro al abrir la cuenta, y crea una contrasena nueva.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Volver } from '../componentes/ui'
import MarcoPublico from './MarcoPublico'

export default function Recuperar() {
  const [datos, setDatos] = useState({ email: '', cedula: '', celular: '', nueva: '', confirmar: '' })
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [lista, setLista] = useState(false)

  function cambiar(campo) {
    return (e) => setDatos({ ...datos, [campo]: e.target.value })
  }

  async function enviar(evento) {
    evento.preventDefault()
    setError('')
    if (datos.nueva !== datos.confirmar) {
      setError('Las contraseñas no coinciden')
      return
    }
    setEnviando(true)
    try {
      const { confirmar, ...cuerpo } = datos
      await api.post('/auth/recuperar-password', cuerpo, { sinRenovar: true })
      setLista(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  if (lista) {
    return (
      <MarcoPublico>
        <div className="text-center">
          <div className="confirmado mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-marca-100 text-3xl text-marca-700">✓</div>
          <h1 className="text-4xl font-bold tracking-tight text-marca-700">Contraseña actualizada</h1>
          <p className="mt-2 text-marca-500">Ya puedes ingresar con tu contraseña nueva.</p>
          <Link to="/app/login" className="boton-vivo mt-8 inline-block w-full rounded-xl bg-marca-700 px-4 py-3 text-sm font-semibold text-white hover:bg-marca-800">
            Ingresar
          </Link>
        </div>
      </MarcoPublico>
    )
  }

  return (
    <MarcoPublico>
      <Volver a="/app/login" className="mb-6 self-start">Volver a ingresar</Volver>
      <h1 className="text-4xl font-bold tracking-tight text-marca-700">Recupera tu contraseña</h1>
      <p className="mb-7 mt-2 text-marca-500">
        Confirma los datos con los que abriste tu cuenta y crea una contraseña nueva.
      </p>
      <form onSubmit={enviar} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Campo etiqueta="Correo" type="email" required autoComplete="username" value={datos.email} onChange={cambiar('email')} />
        </div>
        <Campo etiqueta="Cédula" inputMode="numeric" required pattern="\d{6,10}" title="Entre 6 y 10 dígitos"
               value={datos.cedula} onChange={cambiar('cedula')} />
        <Campo etiqueta="Celular" inputMode="numeric" required pattern="3\d{9}" title="10 dígitos, empieza por 3"
               placeholder="3001234567" value={datos.celular} onChange={cambiar('celular')} />
        <Campo etiqueta="Contraseña nueva" type="password" required minLength={10} autoComplete="new-password"
               ayuda="Mín. 10 caracteres, letras y números" value={datos.nueva} onChange={cambiar('nueva')} />
        <Campo etiqueta="Repite la contraseña" type="password" required autoComplete="new-password"
               value={datos.confirmar} onChange={cambiar('confirmar')} />
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="sm:col-span-2">
          <Boton type="submit" cargando={enviando} className="w-full py-3">Cambiar contraseña</Boton>
        </div>
      </form>
      <p className="mt-6 text-xs text-slate-500">
        Por seguridad, tras varios intentos con datos que no coinciden el usuario queda bloqueado unos minutos.
      </p>
    </MarcoPublico>
  )
}
