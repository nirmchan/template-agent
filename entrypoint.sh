#!/bin/bash

# Custom CA support: mount a PEM file or provide URL(s).
#   CUSTOM_CA_PATH — path to a mounted PEM file (preferred, no network call)
#   CUSTOM_CA_URL  — URL(s) to download PEM from (comma-separated for multiple certs)
#                    Examples:
#                      Single:   CUSTOM_CA_URL="https://example.com/cert.pem"
#                      Multiple: CUSTOM_CA_URL="https://example.com/cert1.pem,https://example.com/cert2.pem"
CA_PEMS=()

if [ -n "$CUSTOM_CA_PATH" ] && [ -f "$CUSTOM_CA_PATH" ]; then
  CA_PEMS=("$CUSTOM_CA_PATH")
elif [ -n "$CUSTOM_CA_URL" ]; then
  # Split CUSTOM_CA_URL by comma and download each certificate
  IFS=',' read -ra URLS <<< "$CUSTOM_CA_URL"
  for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    # Trim whitespace
    url=$(echo "$url" | xargs)
    if [ -n "$url" ]; then
      tmp_ca="/tmp/custom-ca-$i.pem"
      if curl -so "$tmp_ca" "$url"; then
        CA_PEMS+=("$tmp_ca")
        echo "INFO: Successfully fetched CA from $url" >&2
      else
        echo "WARN: Failed to fetch CA from $url, skipping" >&2
      fi
    fi
  done
fi

if [ ${#CA_PEMS[@]} -gt 0 ]; then
  # Use /app (user-writable) instead of /tmp to avoid permission issues with shell redirection
  BUNDLE_PATH="/app/.ca-bundle.pem"

  # Start with system CA bundle
  if command -v python3 &>/dev/null && python3 -m certifi &>/dev/null; then
    cp "$(python3 -m certifi)" "$BUNDLE_PATH"
  elif [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    cp /etc/ssl/certs/ca-certificates.crt "$BUNDLE_PATH"
  elif [ -f /etc/pki/tls/certs/ca-bundle.crt ]; then
    cp /etc/pki/tls/certs/ca-bundle.crt "$BUNDLE_PATH"
  else
    touch "$BUNDLE_PATH"
  fi

  # Append all custom CA certificates to the bundle using cat (not shell redirection)
  for ca_pem in "${CA_PEMS[@]}"; do
    cat "$ca_pem" >> "$BUNDLE_PATH" 2>/dev/null || cat "$ca_pem" | cat >> "$BUNDLE_PATH"
    # Clean up temporary downloads
    [[ "$ca_pem" == /tmp/custom-ca-*.pem ]] && rm -f "$ca_pem"
  done

  export REQUESTS_CA_BUNDLE="$BUNDLE_PATH"
  export SSL_CERT_FILE="$BUNDLE_PATH"
  export CURL_CA_BUNDLE="$BUNDLE_PATH"
  export PIP_CERT="$BUNDLE_PATH"
  export NODE_EXTRA_CA_CERTS="$BUNDLE_PATH"

  echo "INFO: Custom CA bundle configured with ${#CA_PEMS[@]} certificate(s) at $BUNDLE_PATH" >&2
fi

exec "$@"
