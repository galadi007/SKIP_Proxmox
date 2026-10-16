from pydantic import BaseModel, Field

class TemplateMetadata(BaseModel):
    name: str = Field(min_length=3)
    display_name: str = Field(min_length=3)
    summary: str = Field(min_length=1)
    version: str = Field(min_length=5)
    author: str = Field(min_length=3)
    tags: list[str] = Field(default_factory=list)


class ApplicationTemplate(BaseModel):
    """
    Das ist die Root für unser AppTemplate
    """
