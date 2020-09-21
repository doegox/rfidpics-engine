#!/bin/bash

cd web
x-www-browser http://127.0.0.1:8000 &
gnome-terminal -e "python -mSimpleHTTPServer"
