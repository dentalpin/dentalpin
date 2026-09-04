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
RUN npm install

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["npm", "run", "dev"]
