FROM node:22.14-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
FROM node:22.14-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
FROM node:22.14-alpine AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN addgroup -S aegis && adduser -S aegis -G aegis
COPY --from=build --chown=aegis:aegis /app/.next/standalone ./
COPY --from=build --chown=aegis:aegis /app/.next/static ./.next/static
COPY --from=build --chown=aegis:aegis /app/public ./public
USER aegis
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 CMD wget -q -O /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["node", "server.js"]

