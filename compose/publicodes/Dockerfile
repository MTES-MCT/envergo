FROM docker.io/node:20-bookworm-slim

WORKDIR /app/publicodes

COPY ./publicodes/package.json /app/publicodes
COPY ./publicodes/package-lock.json /app/publicodes

RUN npm ci && npm cache clean --force

ENV PATH ./node_modules/.bin/:$PATH
