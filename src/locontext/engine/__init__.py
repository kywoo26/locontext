from .noop import NoopIndexingEngine

__all__ = ["NoopIndexingEngine"]


def __getattr__(name: str) -> object:
    if name == "SQLiteLexicalEngine":
        from importlib import import_module

        module = import_module("locontext.engine.sqlite_lexical")
        return getattr(module, name)
    raise AttributeError(name)
