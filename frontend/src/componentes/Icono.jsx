// Iconos del banco, dibujados como SVG para que se vean igual en cualquier
// computador (antes eran simbolos de texto que cambiaban segun la fuente).
// Uso: <Icono nombre="llave" />  ·  Toman el color del texto que los rodea.

const TRAZOS = {
  // Menus
  tablero: <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>,
  alerta: <><path d="M12 3.5 2.5 20h19L12 3.5z" /><path d="M12 10v4.5M12 17.5v.01" /></>,
  lupa: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  ventanilla: <><rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M6.5 9.5v.01M17.5 14.5v.01" /></>,
  empleados: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.6-3.6 3.2-5.5 6.500-5.500s5.900 1.900 6.500 5.500" /><path d="M16 4.800a3.500 3.500 0 0 1 0 6.400M18.500 14.800c1.700.800 2.700 2.500 3 5.200" /></>,
  ajustes: <><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></>,
  cadena: <><path d="M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1" /><path d="M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1" /></>,
  buzon: <><path d="M3 13.500 5.500 5h13L21 13.500V18a1.500 1.500 0 0 1-1.500 1.500h-15A1.500 1.500 0 0 1 3 18v-4.500z" /><path d="M3 13.500h5l1 2.500h6l1-2.500h5" /></>,
  inicio: <><path d="M3.500 11 12 4l8.500 7" /><path d="M5.500 9.500V20h13V9.500" /></>,
  enviar: <><path d="M21 3 10 14" /><path d="M21 3l-6.500 18-4.500-7-7-4.500L21 3z" /></>,
  usuario: <><circle cx="12" cy="8" r="4" /><path d="M4 20.500c.800-4 3.800-6 8-6s7.200 2 8 6" /></>,
  salir: <><path d="M14 4h4.500A1.500 1.500 0 0 1 20 5.500v13a1.500 1.500 0 0 1-1.500 1.500H14" /><path d="M10 8l-4 4 4 4M6 12h9" /></>,
  // Movimientos
  entrada: <path d="M17 7 7 17M7 9v8h8" />,
  salida: <path d="M7 17 17 7M9 7h8v8" />,
  // Datos y acciones
  llave: <><circle cx="8" cy="15" r="4" /><path d="M11 12l8-8M16 7l3 3M14 9l2 2" /></>,
  codigo: <><rect x="4" y="5" width="16" height="14" rx="3" /><path d="M8 10v4M12 10v4M16 10v4" /></>,
  escudo: <><path d="M12 3l7 3v5c0 4.500-3 8.300-7 10-4-1.700-7-5.500-7-10V6l7-3z" /><path d="m9 12 2.200 2.200L15.500 10" /></>,
  telefono: <><rect x="7" y="2.500" width="10" height="19" rx="2.500" /><path d="M11 18h2" /></>,
  arroba: <><circle cx="12" cy="12" r="3.500" /><path d="M15.500 8.500v5a2.300 2.300 0 0 0 4.500.500V12a8 8 0 1 0-3.500 6.600" /></>,
  ojo: <><path d="M2 12s3.600-6.500 10-6.500S22 12 22 12s-3.600 6.500-10 6.500S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  ojoCerrado: <><path d="M4 4l16 16" /><path d="M9.500 5.900A10 10 0 0 1 12 5.500c6.400 0 10 6.500 10 6.500a17 17 0 0 1-3.300 4M6.200 7.700A17 17 0 0 0 2 12s3.600 6.500 10 6.500a9.600 9.600 0 0 0 4-.900" /><path d="M9.900 9.900a3 3 0 0 0 4.200 4.200" /></>,
  pausa: <><circle cx="12" cy="12" r="9" /><path d="M10 9v6M14 9v6" /></>,
  bloqueo: <><circle cx="12" cy="12" r="9" /><path d="m5.700 5.700 12.600 12.600" /></>,
  check: <path d="m5 12.500 4.500 4.500L19 7.500" />,
  descargar: <><path d="M12 4v11M7.500 11 12 15.500 16.500 11" /><path d="M4.500 19.500h15" /></>,
  imprimir: <><path d="M7 8V3.500h10V8" /><rect x="3.500" y="8" width="17" height="8.500" rx="1.500" /><path d="M7 14h10v6.500H7z" /></>,
  calendario: <><rect x="3.500" y="5" width="17" height="15.500" rx="2" /><path d="M3.500 10h17M8 3v4M16 3v4" /></>,
  mas: <path d="M12 5v14M5 12h14" />,
  // Mensajeria
  chat: <><path d="M20.500 11.500a8 8 0 0 1-11.600 7.100L4 20l1.400-4.300A8 8 0 1 1 20.500 11.500z" /><path d="M8.500 10.500h7M8.500 13.500h4.500" /></>,
  soporte: <><path d="M4 13v-1a8 8 0 0 1 16 0v1" /><rect x="3" y="13" width="4" height="6" rx="1.500" /><rect x="17" y="13" width="4" height="6" rx="1.500" /><path d="M19 19c0 1.500-1.500 2.500-4 2.500h-2" /></>,
  estrella: <path d="m12 3.500 2.600 5.400 5.900.800-4.300 4.100 1 5.800L12 16.800l-5.200 2.800 1-5.800-4.300-4.100 5.900-.800L12 3.500z" />,
  cerrar: <path d="M6 6l12 12M18 6 6 18" />,
  robot: <><rect x="4.500" y="8" width="15" height="11" rx="3" /><path d="M12 4.500V8M9.500 13v.01M14.500 13v.01M9.500 16.200h5" /><circle cx="12" cy="3.800" r="1" /></>,
  copiar: <><rect x="8.5" y="8.5" width="12" height="12" rx="2" /><path d="M15.5 8.5V5a1.5 1.5 0 0 0-1.5-1.5H5A1.5 1.5 0 0 0 3.5 5v9A1.5 1.5 0 0 0 5 15.5h3.5" /></>,
  meta: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" /></>,
  grafica: <><path d="M4 20V10M10 20V4M16 20v-7M21 20H3" /></>,
  puntos: <><circle cx="5.5" cy="12" r="1.2" /><circle cx="12" cy="12" r="1.2" /><circle cx="18.5" cy="12" r="1.2" /></>,
}

export default function Icono({ nombre, className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`shrink-0 ${className}`} fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {TRAZOS[nombre]}
    </svg>
  )
}
