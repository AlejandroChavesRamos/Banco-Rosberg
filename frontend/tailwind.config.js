/** Tailwind: los estilos se escriben como clases (bg-marca-700, rounded-xl, ...) */

// Paleta oficial de Banco Rosberg (los demas tonos de "marca" son mezclas de estos):
//   blanco #FFFFFF · oro #F1B24A · bosque #164A41 · musgo #4D774E · salvia #9DC88D
const marca = {
  50: '#F4F9F1',
  100: '#E6F2E1',
  200: '#CDE4C4',
  300: '#9DC88D', // salvia
  400: '#74A06E',
  500: '#4D774E', // musgo
  600: '#2B5E47',
  700: '#164A41', // bosque
  800: '#113A33',
  900: '#0C2B26',
  950: '#081E1B',
}

// Grises del banco: llevan un toque de verde para no desentonar con la marca.
// Reemplazan a los "slate" de Tailwind, asi todas las pantallas los heredan.
const slate = {
  50: '#F5F8F4',
  100: '#EBF1E9',
  200: '#DAE4D7',
  300: '#BECDBB',
  400: '#8FA391',
  500: '#627868',
  600: '#465F4F',
  700: '#2F4A3D',
  800: '#1C3A30',
  900: '#0C2B26',
  950: '#081E1B',
}

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // El banco usa un solo tema (claro). Se deja 'class' para que las clases "dark:"
  // que aun quedan en pantallas internas no se activen con el tema del sistema.
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        marca,
        slate,
        oro: { DEFAULT: '#F1B24A', claro: '#F8D79B', oscuro: '#A86F0E' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        titulo: ['"Bricolage Grotesque"', 'Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
