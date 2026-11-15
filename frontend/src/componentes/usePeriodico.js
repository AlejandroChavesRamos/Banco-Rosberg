// usePeriodico: ejecuta una funcion al abrir la pantalla y luego cada "ms"
// milisegundos (por ejemplo, revisar alertas nuevas cada 5 segundos).
// Al salir de la pantalla, el reloj se detiene solo.
import { useEffect, useRef } from 'react'

export function usePeriodico(funcion, ms) {
  const ultima = useRef(funcion)
  ultima.current = funcion // siempre usar la version mas reciente de la funcion

  useEffect(() => {
    ultima.current()
    const reloj = setInterval(() => ultima.current(), ms)
    return () => clearInterval(reloj)
  }, [ms])
}
