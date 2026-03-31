FROM docker.io/node:22.13-bookworm-slim

WORKDIR /app

# Install system optipng (arm64 prebuilt binary inside optipng-bin npm package won't work)
RUN apt-get update && apt-get install --no-install-recommends -y optipng \
  && rm -rf /var/lib/apt/lists/*

COPY ./package.json /app
COPY ./package-lock.json /app

RUN npm ci && npm cache clean --force

# Symlink system optipng to the path expected by optipng-bin (npm scripts are disabled via .npmrc)
RUN mkdir -p node_modules/optipng-bin/vendor && \
    ln -sf /usr/bin/optipng node_modules/optipng-bin/vendor/optipng

ENV PATH ./node_modules/.bin/:$PATH
