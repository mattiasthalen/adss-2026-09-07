"""An Analytical Data Storage System: DAS, DAB, DAR, and the destinations that read them."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("adss")
except PackageNotFoundError:  # pragma: no cover - only when running from an unbuilt tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
