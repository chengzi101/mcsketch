class AppError(Exception):
    def __init__(self, message, code="invalid_input", status=400):
        super().__init__(message)
        self.code, self.status = code, status
