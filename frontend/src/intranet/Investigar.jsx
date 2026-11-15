// Investigar una cuenta: resumen, grafo navegable y congelar/descongelar
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Aviso, Boton, Campo, Tarjeta } from '../componentes/ui'
import { cop } from '../formato'
import GrafoCuenta from './GrafoCuenta'

export default function Investigar() {
  const { numero } = useParams() // el numero viene en la direccion: /intranet/investigar/7110...
  const navegar = useNavigate()
  const [busqueda, setBusqueda] = useState(numero ?? '')
  const [resumen, setResumen] = useState(null)
  const [error, setError] = useState('')
  const [motivo, setMotivo] = useState('')
  const [accion, setAccion] = useState({ cargando: false, error: '', mensaje: '' })

  useEffect(() => {
    setBusqueda(numero ?? '')
    setResumen(null)
    setError('')
    if (numero) cargarResumen()
  }, [numero])

  function cargarResumen() {
    api.get(`/analista/cuentas/${numero}`).then(setResumen).catch((e) => setError(e.message))
  }

  async function cambiarEstado(congelar) {
    setAccion({ cargando: true, error: '', mensaje: '' })
    try {
      await api.post(`/analista/cuentas/${numero}/${congelar ? 'congelar' : 'descongelar'}`, { motivo })
      setAccion({ cargando: false, error: '', mensaje: congelar ? 'Cuenta congelada' : 'Cuenta activada de nuevo' })
      setMotivo('')
      cargarResumen()
    } catch (e) {
      setAccion({ cargando: false, error: e.message, mensaje: '' })
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Investigar cuenta</h1>
          <p className="text-sm text-slate-500">Haz clic en cualquier cuenta del grafo para seguir el rastro del dinero.</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); navegar(`/intranet/investigar/${busqueda.trim()}`) }}
              className="flex items-end gap-2">
          <Campo etiqueta="Número de cuenta" inputMode="numeric" pattern="\d{12}" required value={busqueda}
                 onChange={(e) => setBusqueda(e.target.value)} />
          <Boton type="submit">Buscar</Boton>
        </form>
      </div>

      <Aviso>{error}</Aviso>

      {numero && resumen && (
        <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
          <Tarjeta>
            <GrafoCuenta numero={numero} onSeleccionarCuenta={(n) => navegar(`/intranet/investigar/${n}`)} alto={560} />
          </Tarjeta>
          <div className="space-y-5">
            <Tarjeta className="space-y-3">
              <div>
                <div className="text-xs text-slate-500">Titular</div>
                <div className="font-semibold">{resumen.titular}</div>
              </div>
              <Dato texto="Cuenta" valor={resumen.numero} />
              <Dato texto="Tipo" valor={resumen.tipo} />
              <Dato texto="Saldo" valor={cop(resumen.saldo)} />
              <Dato texto="Movimientos" valor={resumen.total_movimientos} />
              <Dato texto="Alertas (históricas)" valor={resumen.total_alertas} />
              <Dato texto="Estado" valor={resumen.estado} resaltar={resumen.estado !== 'activa'} />
            </Tarjeta>
            <Tarjeta className="space-y-3">
              <h3 className="text-sm font-semibold">{resumen.estado === 'congelada' ? 'Descongelar' : 'Congelar'} cuenta</h3>
              <textarea
                className="w-full rounded-xl border-0 bg-white px-3 py-2 text-sm ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-marca-500 dark:bg-slate-900 dark:ring-slate-700"
                rows={2} placeholder="Motivo (obligatorio)" value={motivo} onChange={(e) => setMotivo(e.target.value)}
              />
              <Aviso>{accion.error}</Aviso>
              <Aviso tipo="exito">{accion.mensaje}</Aviso>
              {resumen.estado === 'congelada' ? (
                <Boton className="w-full" cargando={accion.cargando} disabled={motivo.trim().length < 3}
                       onClick={() => cambiarEstado(false)}>Descongelar</Boton>
              ) : (
                <Boton variante="peligro" className="w-full" cargando={accion.cargando} disabled={motivo.trim().length < 3}
                       onClick={() => cambiarEstado(true)}>Congelar</Boton>
              )}
            </Tarjeta>
          </div>
        </div>
      )}

      {!numero && (
        <Tarjeta className="text-sm text-slate-500">
          Escribe un número de cuenta, o entra desde una alerta con el botón “Investigar cuenta”.
        </Tarjeta>
      )}
    </div>
  )
}

function Dato({ texto, valor, resaltar }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{texto}</span>
      <span className={`cifras font-medium capitalize ${resaltar ? 'text-red-600' : ''}`}>{valor}</span>
    </div>
  )
}
