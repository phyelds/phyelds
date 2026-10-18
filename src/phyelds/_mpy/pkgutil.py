"""Stand-in for ``pkgutil``: no namespace packages."""


def extend_path(path: list[str], _name: str) -> list[str]:
    """Return ``path`` unchanged."""
    return path
