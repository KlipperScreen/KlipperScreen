#!/bin/bash

pycodestyle --ignore=E402,W503,W504 --max-line-length=120 --max-doc-length=120 screen.py ks_includes panels
