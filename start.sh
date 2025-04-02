#!/bin/sh

echo $(file /app/tailscaled)
echo $(file /app/tailscale)
echo $(uname -a)

/app/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
/app/tailscale up --auth-key=${TAILSCALE_AUTHKEY} --hostname=octoqueue-topoprint-cloudrun-app
echo "Tailscale started"

ALL_PROXY=socks5://localhost:1055/ octoqueue serve --host 0.0.0.0 --port $PORT
