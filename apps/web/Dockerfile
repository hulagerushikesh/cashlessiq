FROM node:24-bookworm-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
RUN npm ci
COPY --chown=node:node apps/web ./apps/web
COPY packages/api-client ./packages/api-client
COPY packages/contracts/openapi.json ./packages/contracts/openapi.json
RUN chown -R node:node /app/apps/web

FROM base AS builder
ENV CIQ_WEB_STANDALONE=1
RUN npm run build

FROM node:24-bookworm-slim AS production
ENV NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]

# Keep the existing local development stack as the default build target.
FROM base AS development
USER node
EXPOSE 3000
CMD ["npm", "run", "dev", "--workspace", "@cashlessiq/web"]
