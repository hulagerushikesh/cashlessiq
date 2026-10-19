FROM node:24-bookworm-slim
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
USER node
EXPOSE 3000
CMD ["npm", "run", "dev", "--workspace", "@cashlessiq/web"]
