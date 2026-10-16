# CozyClay: pin an upstream release and serve only its compiled browser UI.
# AGPL-3.0-or-later, license + notices copied into public web root.
# No motion/AI sidecars or workspace filesystem exposed.
FROM node:22-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git clone --no-checkout https://github.com/NomaDamas/CozyClay.git . \
    && git checkout 1738d7f8ed8fe4c4ffdc9c6d97bc25792512f763
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npm run build
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /source/dist/ /usr/share/nginx/html/
COPY --from=build /source/LICENSE /usr/share/nginx/html/UPSTREAM-LICENSE.txt
COPY --from=build /source/THIRD_PARTY_NOTICES.md /usr/share/nginx/html/THIRD_PARTY_NOTICES.md
