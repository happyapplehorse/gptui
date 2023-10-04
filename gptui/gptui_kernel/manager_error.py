class ManagerError(Exception):
    ...


class HandlerNotRegisterError(ManagerError):
    def __init__(self, handler, manager=None):
        self.handler = handler
        self.manager = manager
    
    def __str__(self):
        if self.manager is None:
            return f"Handler: {self.handler} is not registered in manager."
        else:
            return f"Handler: {self.handler} is not registered in manager: {self.manager}."


class JobNotRegisterError(ManagerError):
    def __init__(self, job, manager=None):
        self.job = job
        self.manager = manager
    
    def __str__(self):
        if self.manager is None:
            return f"Job: {self.job} is not registered in manager."
        else:
            return f"Job: {self.job} is not registered in manager: {self.manager}."
