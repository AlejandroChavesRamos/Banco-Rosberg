// Marco de las pantallas publicas (login y registro) para computador:
// a la izquierda la marca de Banco Rosberg, a la derecha el formulario.
// En pantallas angostas el panel de la marca se oculta.
import { BotonTema } from '../componentes/ui'

const BENEFICIOS = [
  ['⚿', 'Envía con llaves', 'Transfiere a un celular o correo, sin pedir números de cuenta.'],
  ['⎘', 'Retira sin tarjeta', 'Genera un código y retíralo en cualquier oficina.'],
  ['⛨', 'Protección antifraude', 'Revisamos cada operación en tiempo real para cuidar tu dinero.'],
]

export default function MarcoPublico({ children }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Panel de marca */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-marca-600 via-marca-700 to-marca-900 p-12 text-white lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white text-xl font-bold text-marca-700">R</div>
          <div className="text-xl font-bold tracking-tight">Banco Rosberg</div>
        </div>
        <div className="my-auto max-w-md">
          <h1 className="text-4xl font-bold leading-tight tracking-tight">Tu banco, sin filas y sin sorpresas.</h1>
          <p className="mt-4 text-lg text-white/80">Maneja tu dinero desde el computador con la seguridad de un banco de verdad.</p>
          <ul className="mt-10 space-y-5">
            {BENEFICIOS.map(([icono, titulo, texto]) => (
              <li key={titulo} className="flex gap-4">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/15 text-lg">{icono}</span>
                <div>
                  <div className="font-semibold">{titulo}</div>
                  <div className="text-sm text-white/75">{texto}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-white/60">Banco Rosberg es un banco simulado con fines académicos.</p>
        {/* Circulos decorativos */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-32 right-20 h-80 w-80 rounded-full bg-white/5" />
      </aside>

      {/* Formulario */}
      <section className="flex flex-col">
        <div className="flex justify-end p-6">
          <BotonTema />
        </div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 pb-16">{children}</div>
      </section>
    </div>
  )
}
