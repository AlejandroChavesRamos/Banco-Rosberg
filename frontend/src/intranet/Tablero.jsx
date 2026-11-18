// Tablero: cifras del banco y graficas (libreria Recharts). Se actualiza cada 10 s.
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Aviso, Tarjeta } from '../componentes/ui'
import { usePeriodico } from '../componentes/usePeriodico'
import { cop } from '../formato'

const NOMBRE_REGLA = {
  MONTO_INUSUAL: 'Monto inusual', VELOCIDAD: 'Velocidad', HORARIO_NOCTURNO: 'Nocturno',
  DISPOSITIVO_NUEVO: 'Disp. nuevo', CUENTA_DESTINO_NUEVA: 'Cuenta nueva', DISPOSITIVO_COMPARTIDO: 'Disp. compartido',
  CICLO_DINERO: 'Ciclo', CUENTA_MULA: 'Mula', CERCANIA_FRAUDE: 'Cerca de fraude', CODIGO_RETIRO_FUERZA_BRUTA: 'Fuerza bruta',
}
const COLOR_DECISION = { aprobada: '#4D774E', retenida: '#F1B24A', bloqueada: '#ef4444', rechazada: '#991b1b' }

export default function Tablero() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  usePeriodico(() => {
    api.get('/tablero').then((d) => { setDatos(d); setError('') }).catch((e) => setError(e.message))
  }, 10000)

  if (!datos) return <Aviso>{error}</Aviso>
  const i = datos.indicadores
  const oscuro = document.documentElement.classList.contains('dark')
  const ejes = oscuro ? '#8FA391' : '#627868'
  const tooltip = { contentStyle: { background: oscuro ? '#0f172a' : '#fff', border: '1px solid #2F4A3D33', borderRadius: 12, fontSize: 12 } }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-700">Tablero</h1>
        <p className="text-sm text-slate-500">Visión general de Banco Rosberg. Se actualiza cada 10 segundos.</p>
      </div>

      {/* Indicadores */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Indicador titulo="Alertas abiertas" valor={i.alertas_abiertas} destacado={i.alertas_abiertas > 0} />
        <Indicador titulo="Dinero protegido" valor={cop(i.dinero_protegido)} nota={`${i.operaciones_frenadas} operaciones frenadas`} />
        <Indicador titulo="Transacciones (24 h)" valor={i.transacciones_24h.toLocaleString('es-CO')} />
        <Indicador titulo="Cuentas congeladas" valor={i.cuentas_congeladas} />
        <Indicador titulo="Clientes" valor={i.clientes.toLocaleString('es-CO')} />
        <Indicador titulo="Cuentas" valor={i.cuentas.toLocaleString('es-CO')} />
        <Indicador titulo="Tiquetes de ayuda abiertos" valor={i.tiquetes_abiertos}
                   nota={`${i.tiquetes_sin_asignar} esperando asesor`} destacado={i.tiquetes_sin_asignar > 0} />
        <Indicador titulo="Satisfacción de los clientes" valor={i.satisfaccion ? `${Number(i.satisfaccion).toFixed(1)} / 5` : '—'}
                   nota={`${i.calificaciones} calificaciones`} />
        <Indicador titulo="Solicitudes por responder" valor={i.solicitudes_pendientes} />
        <Indicador titulo="Dinero en el banco" valor={cop(i.dinero_total)} ancho />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Tarjeta>
          <h2 className="mb-4 text-lg font-semibold text-marca-700">Transacciones por hora (últimas 24 h)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={datos.por_hora}>
              <CartesianGrid strokeDasharray="3 3" stroke={ejes} strokeOpacity={0.2} />
              <XAxis dataKey="hora" stroke={ejes} fontSize={11} />
              <YAxis stroke={ejes} fontSize={11} allowDecimals={false} />
              <Tooltip {...tooltip} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="aprobadas" name="Aprobadas" stackId="a" fill="#4D774E" />
              <Bar dataKey="frenadas" name="Frenadas por el motor" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Tarjeta>

        <Tarjeta>
          <h2 className="mb-4 text-lg font-semibold text-marca-700">Alertas por regla</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={datos.por_regla.map((r) => ({ ...r, nombre: NOMBRE_REGLA[r.codigo] ?? r.codigo }))} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={ejes} strokeOpacity={0.2} />
              <XAxis type="number" stroke={ejes} fontSize={11} allowDecimals={false} />
              <YAxis type="category" dataKey="nombre" stroke={ejes} fontSize={11} width={100} />
              <Tooltip {...tooltip} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="abiertas" name="Abiertas" fill="#ef4444" stackId="b" />
              <Bar dataKey={(r) => r.total - r.abiertas} name="Resueltas" fill="#8FA391" stackId="b" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Tarjeta>

        <Tarjeta>
          <h2 className="mb-4 text-lg font-semibold text-marca-700">Decisiones del motor (transferencias, 7 días)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={datos.decisiones} dataKey="total" nameKey="estado" innerRadius={60} outerRadius={95} paddingAngle={2}>
                {datos.decisiones.map((d) => <Cell key={d.estado} fill={COLOR_DECISION[d.estado]} />)}
              </Pie>
              <Tooltip {...tooltip} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Tarjeta>

        <Tarjeta className="space-y-3 text-sm">
          <h2 className="text-lg font-semibold text-marca-700">¿Cómo leer este tablero?</h2>
          <p className="text-slate-500">
            <strong className="text-slate-700">Dinero protegido</strong> es la suma de las operaciones que el
            motor retuvo o bloqueó, o que un analista rechazó: dinero que no llegó a manos de un posible estafador.
          </p>
          <p className="text-slate-500">
            Casi todas las transferencias deben salir <span className="font-semibold text-marca-600">aprobadas</span>: un motor
            que frena demasiado molesta a los clientes honestos. Las <span className="font-semibold text-amber-500">retenidas</span>{' '}
            esperan la decisión de un analista.
          </p>
        </Tarjeta>
      </div>
    </div>
  )
}

function Indicador({ titulo, valor, nota, destacado, ancho }) {
  return (
    <Tarjeta className={ancho ? 'col-span-2' : ''}>
      <div className="text-xs font-medium text-slate-500">{titulo}</div>
      <div className={`cifras mt-1 text-2xl font-bold tracking-tight ${destacado ? 'text-red-600' : ''}`}>{valor}</div>
      {nota && <div className="mt-1 text-xs text-slate-500">{nota}</div>}
    </Tarjeta>
  )
}
