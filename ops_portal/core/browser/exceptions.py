class BrowserLoginRequired(Exception):
    """User interaction required (headed login) before automation can proceed."""
    pass


class BrowserStartupFailed(Exception):
    """Browser could not be started or attached."""
    pass
