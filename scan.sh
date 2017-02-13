#!/bin/bash

(
  cd web
  make
)
(
  cd scanner
  ./main.py ../web/albums ../web/cache/
)
