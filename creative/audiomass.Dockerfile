# Upstream https://github.com/pkalogiros/AudioMass (MIT; see upstream LICENSE)
# Pin the source so upgrades are deliberate.
FROM alpine/git:2.47.2 AS source
WORKDIR /source
RUN git clone --no-checkout https://github.com/pkalogiros/AudioMass.git . \
    && git checkout 21f5ee1362a47be6f0dbe6e4969a15e43d21b044
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=source /source/src/ /usr/share/nginx/html/
COPY --from=source /source/LICENSE /usr/share/nginx/html/UPSTREAM-LICENSE

COPY --from=source /source/THIRD_PARTY_NOTICES.md /usr/share/nginx/html/THIRD_PARTY_NOTICES.md
