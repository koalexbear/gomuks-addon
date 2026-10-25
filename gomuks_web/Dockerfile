# Commit image tags are produced by upstream CI; no floating latest image.
ARG BUILD_ARCH=amd64
FROM dock.mau.dev/gomuks/gomuks:b1ba2099e9d4c0068c7e614d7141b001848369c5-amd64 AS upstream-amd64
FROM dock.mau.dev/gomuks/gomuks:b1ba2099e9d4c0068c7e614d7141b001848369c5-arm64 AS upstream-aarch64
FROM upstream-${BUILD_ARCH} AS runtime
RUN apk add --no-cache nginx python3 py3-yaml py3-bcrypt \
    && mkdir -p /run/nginx /opt/addon
COPY rootfs/ /opt/addon/
ENV GOMUKS_ROOT=/data/gomuks
ENTRYPOINT ["python3", "/opt/addon/start.py"]
