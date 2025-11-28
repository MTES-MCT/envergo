#!/bin/bash
# This script is ran by scalingo at the end of the build process

# Interrupt script on error
set -e

compress_enabled() {
python << END
import sys

from environ import Env

env = Env(COMPRESS_ENABLED=(bool, True))
if env('COMPRESS_ENABLED'):
    sys.exit(0)
else:
    sys.exit(1)

END
}

echo "Starting the post_compile hook"

echo "Installing npm dev dependencies for assets generation."
npm ci --dev

# This is required because we disabled all npm scripts in .npmrc
node node_modules/optipng-bin/lib/install.js
npm run build

echo "Uninstall dev dependencies to prevent bloating /staticfiles"
npm prune --production

if compress_enabled
then
  python manage.py compress --force
fi

# not using collectstatic --clear because it takes ages
rm staticfiles -Rf
python manage.py collectstatic --noinput

python manage.py compilemessages -l fr -i .scalingo -i .venv

echo "Leaving the post_compile hook"
