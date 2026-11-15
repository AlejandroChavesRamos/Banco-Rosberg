import colors from 'tailwindcss/colors'

/** Tailwind: los estilos se escriben como clases (bg-marca-600, rounded-xl, ...) */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class', // el modo oscuro se activa poniendo la clase "dark" en <html>
  theme: {
    extend: {
      colors: {
        marca: colors.emerald, // verde esmeralda de Banco Rosberg
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
