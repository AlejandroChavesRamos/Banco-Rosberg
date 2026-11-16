// Pagina para direcciones que no existen. "volver" es a donde lleva el boton.
import { Link } from 'react-router-dom'
import { Logo } from './ui'

export default function NoEncontrado({ volver = '/app/login', textoVolver = 'Ir al inicio', completa = true }) {
  const contenido = (
    <div className="mx-auto max-w-md text-center">
      <p className="cifras font-titulo text-8xl font-bold tracking-tight text-marca-300">404</p>
      <h1 className="mt-4 text-3xl font-bold tracking-tight text-marca-700">Esta página no existe</h1>
      <p className="mt-3 text-slate-500">
        Puede que la dirección esté mal escrita o que la página se haya movido.
      </p>
      <Link to={volver} className="boton-vivo mt-8 inline-block rounded-full bg-marca-700 px-7 py-3 text-sm font-semibold text-white hover:bg-marca-800">
        {textoVolver}
      </Link>
    </div>
  )
  // Dentro de la app o la intranet ya hay un marco con menu: solo va el contenido
  if (!completa) return <div className="py-16">{contenido}</div>
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-marca-100 px-6 py-3">
        <Link to="/app/login" className="inline-block" aria-label="Banco Rosberg, inicio">
          <Logo />
        </Link>
      </header>
      <main className="grid flex-1 place-items-center px-6 py-16">{contenido}</main>
    </div>
  )
}
