#!/bin/sh
# Helper to re-generate all requirements files

pip-compile base.in
pip-compile local.in
pip-compile production.in
