#!/bin/sh
# Genera un certificado AUTOFIRMADO la primera vez (se guarda en un volumen,
# asi no cambia en cada reinicio). En un servidor real se usaria uno emitido
# por una autoridad (por ejemplo Let's Encrypt).
set -e
DIR=/etc/nginx/certs
if [ ! -f "$DIR/rosberg.crt" ]; then
  mkdir -p "$DIR"
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -keyout "$DIR/rosberg.key" -out "$DIR/rosberg.crt" \
    -subj "/CN=localhost/O=Banco Rosberg (certificado de prueba)" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  chmod 600 "$DIR/rosberg.key"
  echo ">> Certificado autofirmado generado en $DIR"
fi
