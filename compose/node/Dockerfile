FROM docker.io/node:22.13-bookworm-slim

RUN apt-get update && apt-get install -y optipng

WORKDIR /app

# Permet d'exécuter les binaires npm (gulp, sass, etc.) directement par leur nom.
ENV PATH=./node_modules/.bin/:$PATH

COPY ./package.json /app
COPY ./package-lock.json /app
RUN npm ci && npm cache clean --force
