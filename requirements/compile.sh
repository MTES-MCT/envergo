#!/bin/sh
# Helper to re-generate all requirements files

pip-compile --allow-unsafe base.in
pip-compile --allow-unsafe local.in
pip-compile --allow-unsafe production.in
