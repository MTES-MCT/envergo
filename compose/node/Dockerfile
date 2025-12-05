FROM docker.io/node:22.13-bookworm-slim

WORKDIR /app

COPY ./package.json /app
COPY ./package-lock.json /app

RUN npm ci && npm cache clean --force
RUN node node_modules/optipng-bin/lib/install.js

ENV PATH ./node_modules/.bin/:$PATH
