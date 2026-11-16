// =====================================================================
// ui.jsx - Piezas visuales reutilizables (botones, campos, tarjetas...).
// Cada una es una funcion que recibe datos (props) y devuelve HTML (JSX).
// =====================================================================

import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icono from './Icono'

// Simbolo de Banco Rosberg: tres franjas doradas que suben y se apoyan en una
// barra verde. "claro" pone la barra en blanco para fondos verdes.
export function Simbolo({ claro = false, className = 'h-9 w-auto' }) {
  return (
    <svg viewBox="260 369 776 557" className={className} role="img" aria-label="Banco Rosberg">
      <defs>
        <clipPath id="simbolo-recorte">
          <rect x="260" y="379" width="776" height="537" />
        </clipPath>
      </defs>
      <g clipPath="url(#simbolo-recorte)" fill="none" stroke="#F1B24A" strokeWidth="88">
        <path d="M300 956 L508 510 A150 150 0 0 1 645 423 H730" />
        <path d="M468 956 L621 628 A110 110 0 0 1 721 565 H790" />
        <path d="M634 956 L732 746 A70 70 0 0 1 796 706 H860" />
      </g>
      <path d="M677 379 H775 L1026 916 H928 Z" fill={claro ? '#FFFFFF' : '#164A41'} />
    </svg>
  )
}

// Logo completo: simbolo + nombre en dos lineas ("Banco" arriba, "Rosberg" abajo).
// "subtitulo" reemplaza la palabra de arriba (por ejemplo "Intranet").
export function Logo({ subtitulo = 'Banco', claro = false, grande = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <Simbolo claro={claro} className={grande ? 'h-12 w-auto' : 'h-9 w-auto'} />
      <div className="leading-none">
        <div className={`${grande ? 'text-sm' : 'text-xs'} font-medium ${claro ? 'text-white/80' : 'text-marca-500'}`}>{subtitulo}</div>
        <div className={`mt-0.5 font-titulo ${grande ? 'text-2xl' : 'text-xl'} font-bold tracking-tight ${claro ? 'text-white' : 'text-marca-700'}`}>Rosberg</div>
      </div>
    </div>
  )
}

// Enlace "Volver" con flecha, para las pantallas que no tienen menu.
// "claro" lo pone en blanco para fondos verdes.
export function Volver({ a, children = 'Volver', claro = false, className = '' }) {
  return (
    <Link
      to={a}
      className={`group inline-flex items-center gap-1.5 text-sm font-medium ${claro ? 'text-white' : 'text-marca-700'} ${className}`}
    >
      <svg viewBox="0 0 20 20" className="h-4 w-4 transition-transform duration-200 group-hover:-translate-x-1" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 4l-6 6 6 6" />
      </svg>
      <span className="enlace-vivo">{children}</span>
    </Link>
  )
}

// Boton. variante: 'principal' | 'acento' | 'secundario' | 'peligro'
export function Boton({ variante = 'principal', cargando, children, className = '', ...resto }) {
  const estilos = {
    principal: 'bg-marca-700 text-white hover:bg-marca-800 disabled:bg-marca-700/50',
    acento: 'bg-oro text-marca-900 hover:bg-oro-claro disabled:bg-oro/50',
    secundario: 'bg-white text-marca-700 ring-1 ring-marca-200 hover:bg-marca-50',
    peligro: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50',
  }
  return (
    <button
      className={`boton-vivo inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold ${estilos[variante]} ${className}`}
      disabled={cargando || resto.disabled}
      {...resto}
    >
      {cargando && <Girando />}
      {children}
    </button>
  )
}

// Campo de formulario con etiqueta.
// Si es de contrasena (type="password") trae un boton de "ojo" para verla.
export function Campo({ etiqueta, ayuda, type = 'text', ...resto }) {
  const esClave = type === 'password'
  const [visible, setVisible] = useState(false)
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-marca-800">{etiqueta}</span>
      <span className="relative block">
        <input
          type={esClave && visible ? 'text' : type}
          className={`w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm text-marca-900 ring-1 ring-marca-200 transition-shadow placeholder:text-slate-400 hover:ring-marca-300 focus:outline-none focus:ring-2 focus:ring-marca-500 ${esClave ? 'pr-11' : ''}`}
          {...resto}
        />
        {esClave && (
          <button
            type="button"
            onClick={() => setVisible(!visible)}
            className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-xl text-marca-500 hover:text-marca-700"
            aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            aria-pressed={visible}
          >
            <Icono nombre={visible ? 'ojoCerrado' : 'ojo'} />
          </button>
        )}
      </span>
      {ayuda && <span className="mt-1 block text-xs text-slate-500">{ayuda}</span>}
    </label>
  )
}

// Lista desplegable
export function Selector({ etiqueta, opciones, ...resto }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-marca-800">{etiqueta}</span>
      <select
        className="w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm text-marca-900 ring-1 ring-marca-200 hover:ring-marca-300 focus:outline-none focus:ring-2 focus:ring-marca-500"
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
    <div className={`rounded-3xl bg-white p-6 shadow-sm shadow-marca-900/5 ring-1 ring-marca-100 ${className}`}>
      {children}
    </div>
  )
}

// Titulo de una pantalla interna, con una linea de apoyo y acciones a la derecha
export function Encabezado({ titulo, children, acciones }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">{titulo}</h1>
        {children && <p className="mt-1 text-sm text-slate-500">{children}</p>}
      </div>
      {acciones}
    </div>
  )
}

// Mensaje de exito, error o advertencia.
// role="alert": los lectores de pantalla lo anuncian apenas aparece.
export function Aviso({ tipo = 'error', children }) {
  if (!children) return null
  const estilos = {
    error: 'bg-red-50 text-red-800 ring-red-200',
    exito: 'bg-marca-50 text-marca-800 ring-marca-200',
    advertencia: 'bg-amber-50 text-amber-900 ring-amber-200',
  }
  return (
    <div role={tipo === 'exito' ? 'status' : 'alert'} className={`rounded-xl px-4 py-3 text-sm ring-1 ${estilos[tipo]}`}>
      {children}
    </div>
  )
}

// Lo que se muestra cuando una lista no tiene nada: dice que pasa y que hacer
export function EstadoVacio({ icono = 'buzon', titulo, children, accion }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-marca-50 text-marca-500">
        <Icono nombre={icono} className="h-7 w-7" />
      </span>
      <h3 className="mt-4 font-titulo text-lg font-semibold text-marca-700">{titulo}</h3>
      {children && <p className="mt-1 max-w-xs text-sm text-slate-500">{children}</p>}
      {accion && <div className="mt-5">{accion}</div>}
    </div>
  )
}

// Etiqueta pequena de color (por ejemplo el estado de una transaccion)
export function Insignia({ color, children }) {
  return <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>{children}</span>
}

// Circulo girando (cargando)
export function Girando() {
  return <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" role="status" aria-label="Cargando" />
}

// Lista o tarjeta que aun esta trayendo sus datos
export function Cargando({ texto = 'Cargando' }) {
  return (
    <div className="flex items-center justify-center gap-3 p-12 text-sm text-marca-500">
      <Girando />
      {texto}
    </div>
  )
}

export function PantallaCargando() {
  return (
    <div className="grid min-h-screen place-items-center text-marca-600">
      <Girando />
    </div>
  )
}
