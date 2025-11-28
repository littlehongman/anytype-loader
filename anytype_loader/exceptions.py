class AnytypeAPIError(Exception):
    """Fatal errors from Anytype API or transport."""


class AnytypeAuthError(AnytypeAPIError):
    """Authentication/authorization failures."""
