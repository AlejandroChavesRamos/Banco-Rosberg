// Pantalla de inicio de sesion de la App Rosberg
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Aviso, Boton, Campo, PantallaCargando } from '../componentes/ui'
import { useSesion } from '../sesion'
import MarcoPublico from './MarcoPublico'
import SeccionesInicio from './SeccionesInicio'

export default function Login() {
  const { usuario, cargando, iniciarSesion } = useSesion()
  const navegar = useNavigate()
  // useState guarda datos que cambian; al cambiarlos, React vuelve a dibujar
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (cargando) return <PantallaCargando />
  if (usuario) return <Navigate to="/app" replace />

  async function entrar(evento) {
    evento.preventDefault() // evita que el navegador recargue la pagina
    setError('')
    setEnviando(true)
    try {
      const r = await iniciarSesion(email, password)
      navegar(r.debe_cambiar_password ? '/app/cambiar-clave' : '/app')
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <MarcoPublico secciones={<SeccionesInicio />}>
      <h1 className="font-titulo text-4xl font-bold tracking-tight text-marca-700">Hola de nuevo</h1>
      <p className="mb-8 mt-2 text-marca-500">Ingresa a tu banca en línea.</p>

      <form onSubmit={entrar} className="space-y-5">
        <Campo etiqueta="Correo" type="email" required autoComplete="username"
               value={email} onChange={(e) => setEmail(e.target.value)} />
        <Campo etiqueta="Contraseña" type="password" required autoComplete="current-password"
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="-mt-2 text-right">
          <Link to="/app/recuperar" className="enlace-vivo text-sm font-medium text-marca-700">¿Olvidaste tu contraseña?</Link>
        </div>
        <Aviso>{error}</Aviso>
        <Boton type="submit" cargando={enviando} className="w-full py-3 text-base">Ingresar</Boton>
      </form>

      <p className="mt-8 text-sm text-marca-500">
        ¿No tienes cuenta?{' '}
        <Link to="/app/registro" className="enlace-vivo font-semibold text-marca-700">Ábrela en minutos</Link>
      </p>
      <p className="mt-12 text-xs text-slate-400">
        ¿Eres empleado? Usa la <Link to="/intranet" className="underline hover:text-marca-700">Intranet Rosberg</Link>
      </p>
    </MarcoPublico>
  )
}
