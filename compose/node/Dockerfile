FROM docker.io/node:22.13-bookworm-slim

WORKDIR /app

COPY ./package.json /app
COPY ./package-lock.json /app

RUN npm install && npm cache clean --force

ENV PATH ./node_modules/.bin/:$PATH
