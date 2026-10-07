# Imagen de inicialización: alpine (tiene shell) + el binario mc de Chainguard.
# La imagen oficial minio/mc dejó de publicarse y la de Chainguard no trae shell.
FROM chainguard/minio-client:latest AS mc
FROM alpine:3.22
COPY --from=mc /usr/bin/mc /usr/bin/mc
ENTRYPOINT ["/bin/sh"]
