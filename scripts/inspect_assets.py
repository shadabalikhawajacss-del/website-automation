#!/usr/bin/env python3
from rtbdi_assistant.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["inspect-assets", *(__import__("sys").argv[1:])]))
