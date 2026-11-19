ARG BUILD_FROM=ghcr.io/home-assistant/base:3.24
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ALEXA_MANAGER_DATA_DIR=/data

RUN apk add --no-cache python3 py3-pip py3-virtualenv

COPY rootfs /

RUN python3 -m virtualenv /opt/alexa-manager-venv \
    && /opt/alexa-manager-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/alexa-manager-venv/bin/pip install --no-cache-dir -r /app/requirements.txt \
    && chmod a+x /run.sh \
    && mkdir -p /data

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=1.2.1
LABEL io.hass.type="app" io.hass.arch="${BUILD_ARCH}" io.hass.version="${BUILD_VERSION}"

CMD [ "/run.sh" ]
