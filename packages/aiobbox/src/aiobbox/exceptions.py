class BaseError(Exception):
    pass

class ConnectionError(BaseError):
    pass

class RegisterFailed(BaseError):
    pass