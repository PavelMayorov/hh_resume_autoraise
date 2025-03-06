from contextlib import suppress

from .service import Service

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        Service().run()
