// =====================================================================
// Avisos flotantes ("toasts"): confirman una accion abajo a la derecha y
// desaparecen solos a los 4 segundos.
//
// Uso en cualquier pantalla:
//   const avisar = useAviso()
//   avisar('Llave registrada')            // exito (por defecto)
//   avisar('No se pudo copiar', 'error')
// =====================================================================
import { createContext, useCallback, useContext, useRef, useState } from 'react'
import Icono from './Icono'

const AvisosContexto = createContext(() => {})
const DURACION_MS = 4000

export function AvisosProvider({ children }) {
  const [avisos, setAvisos] = useState([])
  const siguienteId = useRef(1)

  const quitar = useCallback((id) => setAvisos((lista) => lista.filter((a) => a.id !== id)), [])

  const avisar = useCallback((texto, tipo = 'exito') => {
    const id = siguienteId.current++
    setAvisos((lista) => [...lista.slice(-2), { id, texto, tipo }]) // como maximo 3 a la vez
    setTimeout(() => quitar(id), DURACION_MS)
  }, [quitar])

  return (
    <AvisosContexto.Provider value={avisar}>
      {children}
      {/* aria-live: los lectores de pantalla leen cada aviso nuevo */}
      <div className="no-imprimir pointer-events-none fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-3" aria-live="polite">
        {avisos.map((a) => (
          <div
            key={a.id}
            role={a.tipo === 'error' ? 'alert' : 'status'}
            className={`aviso-entra pointer-events-auto flex items-start gap-3 rounded-2xl p-4 text-sm shadow-xl ${
              a.tipo === 'error' ? 'bg-red-700 text-white shadow-red-900/20' : 'bg-marca-700 text-white shadow-marca-900/30'
            }`}
          >
            <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full ${a.tipo === 'error' ? 'bg-white/20' : 'bg-oro text-marca-900'}`}>
              <Icono nombre={a.tipo === 'error' ? 'alerta' : 'check'} className="h-3.5 w-3.5" />
            </span>
            <p className="flex-1 leading-snug">{a.texto}</p>
            <button onClick={() => quitar(a.id)} className="-m-1 rounded-lg p-1 text-white/70 hover:text-white" aria-label="Cerrar aviso">
              <Icono nombre="cerrar" className="h-4 w-4" />
            </button>
            {/* Barra que se va vaciando: muestra cuanto le queda al aviso */}
            <span className="aviso-tiempo absolute inset-x-4 bottom-1.5 h-0.5 rounded-full bg-white/40" />
          </div>
        ))}
      </div>
    </AvisosContexto.Provider>
  )
}

export function useAviso() {
  return useContext(AvisosContexto)
}
