// Mi perfil: los datos del cliente. La cedula y el celular llegan del backend
// ya enmascarados (solo los ultimos digitos); la pantalla nunca recibe el dato completo.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icono from '../componentes/Icono'
import { Aviso, Cargando, Encabezado, Tarjeta } from '../componentes/ui'
import { fechaHora } from '../formato'

export default function Perfil() {
  const [perfil, setPerfil] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/perfil').then(setPerfil).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="space-y-6">
      <Encabezado titulo="Mi perfil">Los datos con los que el banco te identifica.</Encabezado>
      <Aviso>{error}</Aviso>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
        <Tarjeta className="p-0">
          {!perfil ? (
            !error && <Cargando texto="Cargando tus datos" />
          ) : (
            <>
              <div className="flex items-center gap-4 border-b border-marca-100 p-6">
                <span className="grid h-16 w-16 place-items-center rounded-full bg-marca-700 font-titulo text-2xl font-bold text-white">
                  {iniciales(perfil.nombre)}
                </span>
                <div>
                  <div className="font-titulo text-xl font-semibold text-marca-700">{perfil.nombre}</div>
                  <div className="text-sm text-slate-500">Cliente desde {fechaHora(perfil.cliente_desde)}</div>
                </div>
              </div>
              <dl className="divide-y divide-marca-100">
                <Dato icono="arroba" etiqueta="Correo">{perfil.email}</Dato>
                <Dato icono="usuario" etiqueta="Cédula">{perfil.cedula ?? 'Sin registrar'}</Dato>
                <Dato icono="telefono" etiqueta="Celular">{perfil.celular ?? 'Sin registrar'}</Dato>
                <Dato icono="ventanilla" etiqueta="Cuentas">{perfil.cuentas}</Dato>
              </dl>
            </>
          )}
        </Tarjeta>

        <Tarjeta className="space-y-4 text-sm">
          <h2 className="text-lg font-semibold text-marca-700">Seguridad</h2>
          <p className="text-slate-500">
            Mostramos solo los últimos dígitos de tu cédula y tu celular. Para corregir un dato, acércate a una
            oficina del banco.
          </p>
          <Link to="/app/cambiar-clave" className="boton-vivo boton-sombra inline-flex items-center gap-2 rounded-xl bg-marca-700 px-4 py-2.5 font-semibold text-white hover:bg-marca-800">
            <Icono nombre="escudo" className="h-4 w-4" />
            Cambiar contraseña
          </Link>
        </Tarjeta>
      </div>
    </div>
  )
}

function Dato({ icono, etiqueta, children }) {
  return (
    <div className="flex items-center gap-4 px-6 py-4">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-marca-50 text-marca-600">
        <Icono nombre={icono} />
      </span>
      <div>
        <dt className="text-xs text-slate-500">{etiqueta}</dt>
        <dd className="cifras font-medium text-marca-900">{children}</dd>
      </div>
    </div>
  )
}

// "Juan Perez Gomez" -> "JP"
function iniciales(nombre) {
  return nombre.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')
}
