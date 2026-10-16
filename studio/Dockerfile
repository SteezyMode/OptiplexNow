FROM node:22-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends git python3 && rm -rf /var/lib/apt/lists/*
ARG ULTRABOX_COMMIT=0ba53c39b086231ebd92bb055cb1edb5d2630b60
RUN git clone https://github.com/ultraabox/ultrabox_typescript.git /ultrabox && cd /ultrabox && git checkout --detach "$ULTRABOX_COMMIT"
WORKDIR /ultrabox
COPY StudioBridge.ts studio.css inject.py /studio/
RUN python3 /studio/inject.py /ultrabox /studio
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1
RUN npm ci && npm install --no-save --no-package-lock jquery@3.7.1
RUN npm run build-editor
RUN mkdir -p website/studio-vendor && cp node_modules/jquery/dist/jquery.min.js website/studio-vendor/jquery.min.js && cp node_modules/select2/dist/js/select2.min.js website/studio-vendor/select2.min.js && cp node_modules/select2/dist/css/select2.min.css website/studio-vendor/select2.min.css
RUN python3 - <<'PY'
from pathlib import Path
import re
p=Path("website/index.html")
s=p.read_text()
s=re.sub(r'<script src="https://code\.jquery\.com/jquery-3\.4\.1\.min\.js"\s+integrity="[^"]+"\s+crossorigin="anonymous"></script>','<script src="/studio-vendor/jquery.min.js"></script>',s)
s=s.replace('https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.7/css/select2.min.css','/studio-vendor/select2.min.css')
s=s.replace('https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.7/js/select2.min.js','/studio-vendor/select2.min.js')
s=re.sub(r'<link href="https://fonts\.googleapis\.com[^>]*>', '', s)
p.write_text(s)
PY
FROM python:3.12-alpine
WORKDIR /app
COPY --from=builder /ultrabox/website /app/site
COPY --from=builder /ultrabox/LICENSE.md /app/site/UPSTREAM-LICENSE.md
COPY server.py /app/server.py
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
ENV STUDIO_DB=/data/studio.sqlite3 STUDIO_SITE=/app/site STUDIO_PORT=8080
EXPOSE 8080
CMD ["python3","-u","/app/server.py"]
