// Intro animada del logo: un punto crece girando hasta ser el simbolo del banco,
// se asienta y debajo aparece el nombre del banco. Despues se muestra la pantalla.
// Sale una sola vez por sesion del navegador (no en cada recarga).
import { useEffect, useState } from 'react'
import { Simbolo } from './ui'

const DURACION_MS = 2300

function debeMostrarse() {
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
    return !sessionStorage.getItem('rosberg-intro')
  } catch {
    return true
  }
}

export default function IntroLogo() {
  const [activa, setActiva] = useState(debeMostrarse)

  useEffect(() => {
    if (!activa) return
    try {
      sessionStorage.setItem('rosberg-intro', '1')
    } catch {}
    // Respaldo: si por algo la animacion no avisa que termino, se quita igual
    const reloj = setTimeout(() => setActiva(false), DURACION_MS + 1500)
    return () => clearTimeout(reloj)
  }, [activa])

  if (!activa) return null
  return (
    <div
      className="intro fixed inset-0 z-50 grid place-items-center bg-white"
      aria-hidden="true"
      // Se quita cuando termina la animacion del fondo (no las de sus hijos)
      onAnimationEnd={(e) => e.target === e.currentTarget && setActiva(false)}
    >
      <div className="flex flex-col items-center">
        <div className="intro-cuadro relative z-10 bg-white px-2">
          <Simbolo className="h-28 w-auto" />
        </div>
        <div className="intro-nombre mt-1 font-titulo text-lg font-extrabold uppercase tracking-[0.18em] text-marca-700">
          Banco Rosberg
        </div>
      </div>
    </div>
  )
}
