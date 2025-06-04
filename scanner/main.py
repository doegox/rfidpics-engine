#!/usr/bin/env python3

from TreeWalker import TreeWalker
from CachePath import message
import sys
import os

def main():
    if len(sys.argv) != 3:
        print("usage: {} ALBUM_PATH CACHE_PATH".format(sys.argv[0]))
        return
    try:
        os.umask(0o22)
        TreeWalker(sys.argv[1], sys.argv[2])
    except KeyboardInterrupt:
        message("keyboard", "CTRL+C pressed, quitting.")
        sys.exit(-97)

if __name__ == "__main__":
    main()
