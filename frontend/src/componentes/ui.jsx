// =====================================================================
// ui.jsx - Piezas visuales reutilizables (botones, campos, tarjetas...).
// Cada una es una funcion que recibe datos (props) y devuelve HTML (JSX).
// =====================================================================
import { useEffect, useState } from 'react'

// Logo de Banco Rosberg
export function Logo({ subtitulo }) {
  return (
    <div className="flex items-center gap-2">
      <div className="grid h-9 w-9 place-items-center rounded-xl bg-marca-600 text-lg font-bold text-white shadow-sm">
        R
      </div>
      <div className="leading-tight">
        <div className="font-bold tracking-tight">Rosberg</div>
        {subtitulo && <div className="text-xs text-slate-500 dark:text-slate-400">{subtitulo}</div>}
      </div>
    </div>
  )
}

// Boton. variante: 'principal' | 'secundario' | 'peligro'
export function Boton({ variante = 'principal', cargando, children, className = '', ...resto }) {
  const estilos = {
    principal: 'bg-marca-600 text-white hover:bg-marca-700 disabled:bg-marca-600/50',
    secundario:
      'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700',
    peligro: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50',
  }
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${estilos[variante]} ${className}`}
      disabled={cargando || resto.disabled}
      {...resto}
    >
      {cargando && <Girando />}
      {children}
    </button>
  )
}

// Campo de formulario con etiqueta
export function Campo({ etiqueta, ayuda, ...resto }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{etiqueta}</span>
      <input
        className="w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm ring-1 ring-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-marca-500 dark:bg-slate-900 dark:ring-slate-700"
        {...resto}
      />
      {ayuda && <span className="mt-1 block text-xs text-slate-500">{ayuda}</span>}
    </label>
  )
}

// Lista desplegable
export function Selector({ etiqueta, opciones, ...resto }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{etiqueta}</span>
      <select
        className="w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-marca-500 dark:bg-slate-900 dark:ring-slate-700"
        {...resto}
      >
        {opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.texto}
          </option>
        ))}
      </select>
    </label>
  )
}

// Caja con borde redondeado
export function Tarjeta({ children, className = '' }) {
  return (
    <div className={`rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-900 dark:ring-slate-800 ${className}`}>
      {children}
    </div>
  )
}

// Mensaje de exito, error o advertencia
export function Aviso({ tipo = 'error', children }) {
  if (!children) return null
  const estilos = {
    error: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-300 dark:ring-red-900',
    exito: 'bg-marca-50 text-marca-800 ring-marca-200 dark:bg-marca-950 dark:text-marca-300 dark:ring-marca-900',
    advertencia: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900',
  }
  return <div className={`rounded-xl px-4 py-3 text-sm ring-1 ${estilos[tipo]}`}>{children}</div>
}

// Etiqueta pequena de color (por ejemplo el estado de una transaccion)
export function Insignia({ color, children }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>{children}</span>
}

// Circulo girando (cargando)
export function Girando() {
  return <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
}

export function PantallaCargando() {
  return (
    <div className="grid min-h-screen place-items-center text-marca-600">
      <Girando />
    </div>
  )
}

// Interruptor de modo claro / oscuro
export function BotonTema() {
  const [oscuro, setOscuro] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', oscuro)
    try {
      localStorage.setItem('rosberg-tema', oscuro ? 'oscuro' : 'claro')
    } catch {}
  }, [oscuro])
  return (
    <button
      onClick={() => setOscuro(!oscuro)}
      className="grid h-9 w-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
      title={oscuro ? 'Modo claro' : 'Modo oscuro'}
    >
      {oscuro ? '☀' : '☾'}
    </button>
  )
}
