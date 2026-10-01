# Dev image for docker-compose.yml. Source code arrives at runtime through
# the ./frontend:/app bind mount; this image only provides node plus
# node_modules (seeded into the anonymous /app/node_modules volume).
#
# Production images build from Dockerfile.prod with the repo root as
# context. The multi-stage prod build that used to live here ran
# `npm run build` at image-build time with the default Node heap — the
# 34-layer × 9-locale Nitro build needs >4GB (see Dockerfile.prod) — and
# then discarded the output, because the dev container runs `npm run dev`.
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS dev

WORKDIR /app

COPY package*.json ./
# Stamp the lockfile hash so a freshly seeded volume skips the re-sync.
RUN npm ci --no-audit --no-fund \
 && sha256sum package-lock.json | cut -d' ' -f1 > node_modules/.package-lock.sha256

# Self-healing entrypoint (see file): the anonymous /app/node_modules
# volume shadows this image's modules with whatever was seeded first —
# re-sync on lockfile drift. Lives outside /app so the bind mount
# (./frontend:/app) cannot shadow it.
# Own name: node's base image already ships /usr/local/bin/docker-entrypoint.sh.
COPY node-modules-sync.sh /usr/local/bin/node-modules-sync.sh
ENTRYPOINT ["sh", "/usr/local/bin/node-modules-sync.sh"]

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["npm", "run", "dev"]
