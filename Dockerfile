FROM python:3.12-alpine 

RUN apk update && apk add ca-certificates && rm -rf /var/cache/apk/*

WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml .
COPY uv.lock .
COPY src/ src/
COPY start.sh start.sh
RUN chmod +x start.sh

# Install dependencies
RUN pip install --no-cache-dir .

# Copy Tailscale binaries from the tailscale image on Docker Hub.
COPY --from=docker.io/tailscale/tailscale:stable /usr/local/bin/tailscaled /app/tailscaled
COPY --from=docker.io/tailscale/tailscale:stable /usr/local/bin/tailscale /app/tailscale
RUN mkdir -p /var/run/tailscale /var/cache/tailscale /var/lib/tailscale

# Set environment variables
ENV PORT=8080

# Run the application
CMD ["/app/start.sh"]
