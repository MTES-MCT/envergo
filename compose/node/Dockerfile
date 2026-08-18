FROM docker.io/node:22.13-bookworm-slim

WORKDIR /app

COPY ./package.json /app
COPY ./package-lock.json /app

RUN npm ci && npm cache clean --force

ENV PATH ./node_modules/.bin/:$PATH

# This is required because we disabled all npm scripts in .npmrc
RUN node node_modules/optipng-bin/lib/install.js
