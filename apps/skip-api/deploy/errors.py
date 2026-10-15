class DeployError(Exception):
    """Base class for expected deployment failures."""


class DeploymentForbiddenError(DeployError):
    pass


class InvalidDeploymentError(DeployError):
    pass


class DeploymentConflictError(DeployError):
    pass


class DeploymentNotFoundError(DeployError):
    pass
