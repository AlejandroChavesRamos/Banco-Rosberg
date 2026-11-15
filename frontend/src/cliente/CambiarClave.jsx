// Cambiar contrasena. Obligatorio para clientes creados en ventanilla.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Tarjeta } from '../componentes/ui'
import { useSesion } from '../sesion'

export default function CambiarClave() {
  // Se usa en los dos portales: "portal" dice a que login volver
  const { usuario, cerrarSesion, portal } = useSesion()
  const navegar = useNavigate()
  const [datos, setDatos] = useState({ actual: '', nueva: '', confirmar: '' })
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function guardar(evento) {
    evento.preventDefault()
    setError('')
    if (datos.nueva !== datos.confirmar) {
      setError('Las contraseñas nuevas no coinciden')
      return
    }
    setCargando(true)
    try {
      await api.post('/auth/cambiar-password', { actual: datos.actual, nueva: datos.nueva })
      // El backend cierra todas las sesiones por seguridad: hay que entrar de nuevo
      await cerrarSesion()
      navegar(`/${portal}/login`)
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="max-w-md space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">Cambiar contraseña</h1>
      {usuario?.debeCambiar && (
        <Aviso tipo="advertencia">
          Tu usuario fue creado con una contraseña temporal. Crea una propia para continuar.
        </Aviso>
      )}
      <Tarjeta>
        <form onSubmit={guardar} className="space-y-4">
          <Campo etiqueta="Contraseña actual" type="password" required autoComplete="current-password"
                 value={datos.actual} onChange={(e) => setDatos({ ...datos, actual: e.target.value })} />
          <Campo etiqueta="Nueva contraseña" type="password" required minLength={10} autoComplete="new-password"
                 ayuda="Mínimo 10 caracteres, con letras y números"
                 value={datos.nueva} onChange={(e) => setDatos({ ...datos, nueva: e.target.value })} />
          <Campo etiqueta="Repite la nueva contraseña" type="password" required autoComplete="new-password"
                 value={datos.confirmar} onChange={(e) => setDatos({ ...datos, confirmar: e.target.value })} />
          <Aviso>{error}</Aviso>
          <Boton type="submit" cargando={cargando} className="w-full">Guardar</Boton>
        </form>
      </Tarjeta>
    </div>
  )
}
