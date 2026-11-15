FROM node:20-alpine

# /codigo y no /app: Vite confundiria la carpeta /app con la ruta /app del portal
WORKDIR /codigo

# Primero solo package.json: asi Docker reutiliza las librerias ya instaladas
# mientras no cambien las dependencias
COPY package.json ./
RUN npm install

COPY . .

# Usuario sin privilegios (igual que el backend)
RUN chown -R node:node /codigo
USER node

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
