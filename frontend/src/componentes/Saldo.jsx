// =====================================================================
// Todo lo que tiene que ver con mostrar dinero en el panel del cliente:
//   <CifraAnimada valor={...} />   cuenta hasta el valor y termina EXACTO en el
//   useSaldoOculto()                el boton del "ojo" para ocultar los saldos
//   <Dinero valor={...} />          la cifra animada, o •••••• si esta oculta
// =====================================================================
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { cop } from '../formato'

const CLAVE = 'rosberg-ocultar-saldo'
const SaldoContexto = createContext({ oculto: false, alternar: () => {} })

// Se recuerda en este navegador (si el navegador no deja guardar, igual funciona)
export function SaldoProvider({ children }) {
  const [oculto, setOculto] = useState(() => {
    try {
      return localStorage.getItem(CLAVE) === '1'
    } catch {
      return false
    }
  })
  function alternar() {
    setOculto((antes) => {
      try {
        localStorage.setItem(CLAVE, antes ? '0' : '1')
      } catch {}
      return !antes
    })
  }
  return <SaldoContexto.Provider value={{ oculto, alternar }}>{children}</SaldoContexto.Provider>
}

export function useSaldoOculto() {
  return useContext(SaldoContexto)
}

// Cuenta desde el valor anterior hasta el nuevo en ~0,8 s. Siempre termina en
// la cifra exacta, y quien pidio "menos movimiento" la ve de una vez.
export function CifraAnimada({ valor }) {
  const destino = Number(valor || 0)
  const [mostrado, setMostrado] = useState(destino)
  const desde = useRef(0) // la primera vez cuenta desde cero

  useEffect(() => {
    const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const inicio = desde.current
    if (quieto || inicio === destino) {
      setMostrado(destino)
      desde.current = destino
      return
    }
    const duracion = 800
    const t0 = performance.now()
    let cuadro
    function paso(ahora) {
      const avance = Math.min(1, (ahora - t0) / duracion)
      const suave = 1 - Math.pow(1 - avance, 3) // arranca rapido y frena al final
      setMostrado(avance < 1 ? inicio + (destino - inicio) * suave : destino)
      if (avance < 1) cuadro = requestAnimationFrame(paso)
    }
    cuadro = requestAnimationFrame(paso)
    desde.current = destino
    return () => cancelAnimationFrame(cuadro)
  }, [destino])

  return <span className="cifras">{cop(Math.round(mostrado))}</span>
}

export function Dinero({ valor, animado = true }) {
  const { oculto } = useSaldoOculto()
  if (oculto) return <span aria-label="Saldo oculto">$ ••••••</span>
  return animado ? <CifraAnimada valor={valor} /> : <span className="cifras">{cop(valor)}</span>
}
