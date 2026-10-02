import sys as _sys
from importlib import import_module as _import_module

_module = _import_module("rivals_api.exceptions")
if __name__ == "__main__" and hasattr(_module, "main"):
    _module.main()
else:
    _sys.modules[__name__] = _module
