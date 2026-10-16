# Onionskyn is a self-contained, MIT-licensed browser animation editor.
# Development is early (2026 beta). We pin a known commit and isolate it.
FROM alpine/git:2.47.2 AS upstream
WORKDIR /source
RUN git clone --no-checkout https://github.com/papptimus/Onionskyn.git . \
    && git checkout df36837a6bd48763fa1806ce4d24040821470d3c
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=upstream /source/index.html /usr/share/nginx/html/index.html
COPY --from=upstream /source/LICENSE /usr/share/nginx/html/UPSTREAM-LICENSE.txt
COPY --from=upstream /source/THIRD-PARTY.md /usr/share/nginx/html/THIRD-PARTY.md
