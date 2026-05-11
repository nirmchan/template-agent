## Dockerfile for deep-agents-ui (Next.js).
## Used by compose.aegra.yaml.
##
## Pre-requisite: clone the UI repo into ./deep-agents-ui/
##   git clone https://github.com/langchain-ai/deep-agents-ui.git

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile 2>/dev/null || yarn install
COPY . .
RUN yarn build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["yarn", "start"]
