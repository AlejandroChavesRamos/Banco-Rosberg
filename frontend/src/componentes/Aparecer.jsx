// Hace que su contenido "surja" (suba y aparezca) cuando entra en pantalla al bajar.
import { useEffect, useRef, useState } from 'react'

export default function Aparecer({ children, retraso = 0, className = '' }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    // IntersectionObserver avisa cuando el elemento entra en la ventana
    const observador = new IntersectionObserver(
      ([entrada]) => {
        if (entrada.isIntersecting) {
          setVisible(true)
          observador.disconnect() // solo la primera vez
        }
      },
      { threshold: 0.15 },
    )
    observador.observe(ref.current)
    return () => observador.disconnect()
  }, [])

  return (
    <div ref={ref} className={`aparecer ${visible ? 'visible' : ''} ${className}`} style={{ '--retraso': `${retraso}ms` }}>
      {children}
    </div>
  )
}
