FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./

# Install dependencies exactly as in lockfile
RUN npm ci

COPY . .

# Build time argument for the API URL
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Use the locally installed next binary, NOT npx (which downloads latest)
RUN ./node_modules/.bin/next build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production

# COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]