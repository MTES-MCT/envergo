FROM docker.io/node:20-bookworm-slim

WORKDIR /app

COPY ./package.json /app
COPY ./package-lock.json /app

RUN npm ci && npm cache clean --force

ENV PATH ./node_modules/.bin/:$PATH
