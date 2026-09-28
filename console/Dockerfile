# Build context is the repo root (see .github/workflows/docker-build.yml) for
# consistency with the two Python services, even though this image only needs
# console/. Multi-stage: full node_modules for `next build`, then a slim
# runtime image using Next's standalone output (see next.config.js).

FROM node:20-slim AS builder
WORKDIR /srv
COPY console/package.json console/package-lock.json* ./
RUN npm install
COPY console/ .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /srv
ENV NODE_ENV=production
COPY --from=builder /srv/public ./public
COPY --from=builder /srv/.next/standalone ./
COPY --from=builder /srv/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
