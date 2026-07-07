#!/bin/bash

# Custom CA support: mount a PEM file or provide a URL.
#   CUSTOM_CA_PATH — path to a mounted PEM file (preferred, no network call)
#   CUSTOM_CA_URL  — URL to download PEM from (fallback, hits network per pod)
CA_PEM=""

if [ -n "$CUSTOM_CA_PATH" ] && [ -f "$CUSTOM_CA_PATH" ]; then
  CA_PEM="$CUSTOM_CA_PATH"
elif [ -n "$CUSTOM_CA_URL" ]; then
  if curl -so /tmp/custom-ca.pem "$CUSTOM_CA_URL"; then
    CA_PEM="/tmp/custom-ca.pem"
  else
    echo "WARN: Failed to fetch CA from $CUSTOM_CA_URL, continuing with defaults" >&2
  fi
fi

if [ -n "$CA_PEM" ]; then
  if command -v python3 &>/dev/null && python3 -m certifi &>/dev/null; then
    cp "$(python3 -m certifi)" /tmp/ca-bundle.pem
  elif [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    cp /etc/ssl/certs/ca-certificates.crt /tmp/ca-bundle.pem
  elif [ -f /etc/pki/tls/certs/ca-bundle.crt ]; then
    cp /etc/pki/tls/certs/ca-bundle.crt /tmp/ca-bundle.pem
  else
    cp /dev/null /tmp/ca-bundle.pem
  fi

  cat "$CA_PEM" >> /tmp/ca-bundle.pem
  [ "$CA_PEM" = "/tmp/custom-ca.pem" ] && rm /tmp/custom-ca.pem

  export REQUESTS_CA_BUNDLE=/tmp/ca-bundle.pem
  export SSL_CERT_FILE=/tmp/ca-bundle.pem
  export CURL_CA_BUNDLE=/tmp/ca-bundle.pem
  export PIP_CERT=/tmp/ca-bundle.pem
  export NODE_EXTRA_CA_CERTS=/tmp/ca-bundle.pem
fi

exec "$@"
