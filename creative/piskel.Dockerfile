# Upstream https://github.com/piskelapp/piskel (Apache-2.0).
FROM node:22-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git clone --no-checkout https://github.com/piskelapp/piskel.git . \
    && git checkout bef52beb312e771bf0cbb915d873e8d638842d7a
ENV PUPPETEER_SKIP_DOWNLOAD=1 HUSKY=0
RUN npm ci --no-audit --no-fund \
    && npm run build
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /source/dest/prod/ /usr/share/nginx/html/
COPY --from=build /source/LICENSE /usr/share/nginx/html/UPSTREAM-LICENSE
