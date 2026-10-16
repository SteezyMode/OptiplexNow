# Blockbench GPL-3.0-or-later pinned web editor; source and license retained.
FROM node:22-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git clone --no-checkout https://github.com/JannisX11/blockbench.git . \
    && git checkout 7c92e27d237e365110030d73e92c5d1605f0d311
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npm run build-web
RUN mkdir -p /out \
    && cp -a index.html assets css font lib content lang keymaps themes dist \
       favicon.png icon.png icon_full.png icon_maskable.png manifest.webmanifest /out/ \
    && cp LICENSE.MD /out/UPSTREAM-LICENSE.MD
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /out/ /usr/share/nginx/html/
