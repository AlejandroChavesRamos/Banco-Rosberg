// =====================================================================
// sesion.jsx - Quien esta conectado, en cualquier pantalla.
//
// <SesionProvider portal="app"> envuelve las pantallas de un portal. Dentro,
// cualquier componente puede hacer:   const { usuario, iniciarSesion } = useSesion()
// =====================================================================
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { api, configurarRenovacion, guardarToken } from './api'

const SesionContexto = createContext(null)

function datosUsuario(respuesta) {
  return {
    nombre: respuesta.nombre,
    rol: respuesta.rol,
    debeCambiar: respuesta.debe_cambiar_password,
  }
}

export function SesionProvider({ portal, children }) {
  const [usuario, setUsuario] = useState(null) // null = nadie conectado
  const [cargando, setCargando] = useState(true) // mientras revisamos si habia sesion

  const renovacionEnCurso = useRef(null)

  // Pide un token nuevo usando la cookie segura. Devuelve true/false.
  // IMPORTANTE: si varias partes de la pantalla piden renovar a la vez, todas
  // esperan la MISMA peticion. Si cada una enviara la cookie por su cuenta, la
  // segunda usaria un token ya gastado y el backend lo trataria como un robo
  // de sesion (y cerraria todas las sesiones del usuario).
  function renovar() {
    if (!renovacionEnCurso.current) {
      renovacionEnCurso.current = (async () => {
        try {
          const r = await api.post(`/auth/refresh?portal=${portal}`, undefined, { sinRenovar: true })
          guardarToken(r.access_token)
          setUsuario(datosUsuario(r))
          return true
        } catch {
          guardarToken(null)
          setUsuario(null)
          return false
        }
      })().finally(() => {
        renovacionEnCurso.current = null
      })
    }
    return renovacionEnCurso.current
  }

  // Al abrir la pagina: si quedaba una sesion (cookie), se recupera sola
  useEffect(() => {
    configurarRenovacion(renovar)
    renovar().finally(() => setCargando(false))
  }, [portal])

  async function iniciarSesion(email, password) {
    const r = await api.post('/auth/login', { email, password, portal }, { sinRenovar: true })
    guardarToken(r.access_token)
    setUsuario(datosUsuario(r))
    return r
  }

  async function cerrarSesion() {
    try {
      await api.post(`/auth/logout?portal=${portal}`, undefined, { sinRenovar: true })
    } catch {
      // aunque falle, se borra la sesion local
    }
    guardarToken(null)
    setUsuario(null)
  }

  return (
    <SesionContexto.Provider value={{ portal, usuario, cargando, iniciarSesion, cerrarSesion, renovar }}>
      {children}
    </SesionContexto.Provider>
  )
}

export function useSesion() {
  return useContext(SesionContexto)
}
