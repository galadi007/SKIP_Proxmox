class TemplateError(Exception):
    pass


class TemplateNotFoundError(TemplateError):
    def __init__(self, name: str):
        super().__init__(f"Template '{name}' not found")
        self.name = name


class InvalidTemplateError(TemplateError):
    pass


class DuplicateTemplateError(TemplateError):
    pass


class TemplateAssetNotFoundError(TemplateError):
    def __init__(self, template_name: str, asset: str):
        super().__init__(
            f"Asset '{asset}' not found for template '{template_name}'"
        )
        self.template_name = template_name
        self.asset = asset


class TemplateSourceError(TemplateError):
    pass
