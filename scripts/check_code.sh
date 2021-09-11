#!/bin/bash

pycodestyle --ignore=E226,E301,E302,E303,E402,W503,W504 --max-line-length=120 --max-doc-length=120 screen.py ks_includes panels
