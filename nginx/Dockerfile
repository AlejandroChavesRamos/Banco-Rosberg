# =====================================================================
# nginx de PRODUCCION (dos etapas):
#   1) "compilar": Node convierte las pantallas React en archivos estaticos
#      optimizados (HTML, JS y CSS minificados).
#   2) nginx sirve esos archivos y reenvia /api al backend, con HTTPS.
# La imagen final NO contiene Node ni el codigo fuente: solo lo necesario.
# =====================================================================
FROM node:20-alpine AS compilar
WORKDIR /codigo
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
# openssl: para generar el certificado autofirmado la primera vez
RUN apk add --no-cache openssl
COPY --from=compilar /codigo/dist /usr/share/nginx/html
COPY nginx/rosberg.conf /etc/nginx/conf.d/default.conf
COPY nginx/proxy_comun.conf /etc/nginx/proxy_comun.conf
# Los scripts de /docker-entrypoint.d/ se ejecutan antes de arrancar nginx
COPY nginx/40-certificado.sh /docker-entrypoint.d/40-certificado.sh
RUN chmod +x /docker-entrypoint.d/40-certificado.sh
EXPOSE 80 443
