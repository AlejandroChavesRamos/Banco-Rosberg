// Formatos colombianos para mostrar datos

const pesos = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

// 1500000 -> "$ 1.500.000"
export function cop(valor) {
  return pesos.format(Number(valor || 0))
}

// "2026-11-15T14:30:00" -> "15 nov. 2026, 2:30 p. m."
export function fechaHora(texto) {
  if (!texto) return ''
  return new Date(texto).toLocaleString('es-CO', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// "711087278961" -> "****8961"
export function enmascarar(numero) {
  return numero ? `****${String(numero).slice(-4)}` : ''
}

// Textos y colores para el estado de una transaccion
export const ESTADOS = {
  aprobada: { texto: 'Exitosa', color: 'text-marca-700 bg-marca-50' },
  retenida: { texto: 'En revisión', color: 'text-amber-700 bg-amber-50' },
  bloqueada: { texto: 'Bloqueada', color: 'text-red-700 bg-red-50' },
  rechazada: { texto: 'Rechazada', color: 'text-red-700 bg-red-50' },
}
