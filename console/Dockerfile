# builds the app, then copies just the build output into a smaller final image
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
