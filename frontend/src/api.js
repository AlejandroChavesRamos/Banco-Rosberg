// =====================================================================
// api.js - Unico lugar desde donde las pantallas hablan con el backend.
//
// Seguridad:
//  - El token de acceso se guarda SOLO EN MEMORIA (una variable), nunca en
//    localStorage: si una pagina maliciosa lograra ejecutar codigo (XSS), no
//    lo encontraria guardado en el navegador.
//  - La sesion larga vive en una cookie HttpOnly que JavaScript no puede leer.
//    Cuando el token vence (15 min), se pide otro automaticamente.
//  - Cada llamada envia X-Dispositivo para que el motor antifraude reconozca
//    "tu celular de siempre".
// =====================================================================

let tokenAcceso = null // el token vive aqui, en memoria
let renovarSesion = null // funcion que pide un token nuevo (la define sesion.jsx)

export function guardarToken(token) {
  tokenAcceso = token
}

export function configurarRenovacion(funcion) {
  renovarSesion = funcion
}

// Identificador de ESTE navegador. Se crea una vez y se recuerda.
export function idDispositivo() {
  let id = localStorage.getItem('rosberg-dispositivo')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('rosberg-dispositivo', id)
  }
  return id
}

// Clave unica para una operacion (evita duplicados por doble clic)
export function nuevaClave() {
  return crypto.randomUUID()
}

// Convierte los errores del backend en un mensaje legible
function mensajeDeError(datos, status) {
  if (!datos) return `Error ${status}`
  if (typeof datos.detail === 'string') return datos.detail
  if (Array.isArray(datos.detail)) {
    // Errores de validacion (422): uno por campo
    return datos.detail
      .map((e) => {
        const campo = e.loc?.[e.loc.length - 1]
        const texto = e.msg?.replace('Value error, ', '')
        return campo ? `${campo}: ${texto}` : texto
      })
      .join(' · ')
  }
  return `Error ${status}`
}

/**
 * Hace una peticion a la API.
 *   llamar('GET', '/cuentas')
 *   llamar('POST', '/transferencias', { ... }, { clave: 'abc' })
 */
export async function llamar(metodo, ruta, cuerpo, opciones = {}) {
  const cabeceras = { 'X-Dispositivo': idDispositivo() }
  if (cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json'
  if (tokenAcceso) cabeceras['Authorization'] = `Bearer ${tokenAcceso}`
  if (opciones.clave) cabeceras['Idempotency-Key'] = opciones.clave

  let respuesta
  try {
    respuesta = await fetch(`/api${ruta}`, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
      credentials: 'same-origin', // envia la cookie de sesion
    })
  } catch {
    // La red fallo antes de obtener respuesta
    const error = new Error('Sin conexión con el banco. Revisa tu conexión e intenta de nuevo.')
    error.status = 0
    throw error
  }

  // Token vencido: pedir uno nuevo y repetir UNA vez
  if (respuesta.status === 401 && !opciones.sinRenovar && renovarSesion) {
    const renovada = await renovarSesion()
    if (renovada) return llamar(metodo, ruta, cuerpo, { ...opciones, sinRenovar: true })
  }

  const datos = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    // Respuesta sin JSON y con error de servidor: el contenedor del backend esta
    // apagado o reiniciandose (el proxy no lo encuentra)
    const mensaje =
      !datos && respuesta.status >= 500
        ? 'El servicio del banco no responde en este momento. Intenta de nuevo en unos segundos.'
        : mensajeDeError(datos, respuesta.status)
    const error = new Error(mensaje)
    error.status = respuesta.status
    throw error
  }
  return datos
}

export const api = {
  get: (ruta, op) => llamar('GET', ruta, undefined, op),
  post: (ruta, cuerpo, op) => llamar('POST', ruta, cuerpo ?? {}, op),
  patch: (ruta, cuerpo, op) => llamar('PATCH', ruta, cuerpo, op),
  delete: (ruta, op) => llamar('DELETE', ruta, undefined, op),
}
