from typing import Literal, List

from pydantic import BaseModel, Field


class ProjectVersion(BaseModel):
    major              : int = Field(... , description="The major version of the project")
    minor              : int = Field(... , description="The minor version of the project")
    build_ground       : int = Field(..., description="The ground number to subtract from the total amount of commits to calculate the build number")
    # excluded fields
    resulting_version  : str = Field(None, exclude=True, description="The version of the project")


class ComponentConfig(BaseModel):
    type           : Literal[None]   = Field(None, description="The type of the component")
    name           : str             = Field(..., description="The name of the component")
    depends_on     : List[str]       = Field(default_factory=list, description="The components this component depends on")
    # excluded fields
    parent_project : "ProjectConfig" = Field(None, exclude=True, description="The root folder of the component")

    @property
    def component_root(self):
        return f"{self.parent_project.project_root}/{self.name}"


class ProjectConfig(BaseModel):
    tenant       : str = Field(..., description="The tenant of the project. Either the tenant ID or the tenant name (i.e. abc.onmicrosoft.com)")
    version      : ProjectVersion
    # excluded fields
    components   : List[ComponentConfig] = Field(default_factory=list, exclude=True)
    project_root : str = Field(None, exclude=True, description="The root folder of the project")
    _components_by_name : dict[str, ComponentConfig] = Field(default_factory=None, exclude=True, description="The components by name")

    def get_component(self, name: str):
        component = self._components_by_name.get(name, None)
        if component is None:
            raise ValueError(f"Component '{name}' not found in the project configuration. Available components: {list(self._components_by_name.keys())}")
        return component
