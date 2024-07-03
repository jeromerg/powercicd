from typing import Literal, List

from pydantic import BaseModel, Field, PrivateAttr
from typing_extensions import Annotated


class ProjectVersion(BaseModel):
    major              : Annotated[int, Field(description="The major version of the project")]
    minor              : Annotated[int, Field(description="The minor version of the project")]
    build_ground       : Annotated[int, Field(description="The ground number to subtract from the total amount of commits to calculate the build number")]
    # excluded fields
    resulting_version  : Annotated[str, Field(exclude=True, description="The version of the project")] = None


class ComponentConfig(BaseModel):
    type           : Annotated[Literal[None]   , Field(description="The type of the component")] = None
    depends_on     : Annotated[List[str]       , Field(default_factory=list, description="The components this component depends on")]
    # excluded fields
    name           : Annotated[str             , Field(exclude=True, description="The name of the component")] = None
    parent_project : Annotated["ProjectConfig" , Field(exclude=True, description="The root folder of the component")] = None

    @property
    def component_root(self):
        return f"{self.parent_project.project_root}/{self.name}"


class ProjectConfig(BaseModel):
    tenant              : Annotated[str, Field(description="The tenant of the project. Either the tenant ID or the tenant name (i.e. abc.onmicrosoft.com)")]
    version             : Annotated[ProjectVersion, Field(description="The version of the project")]
    # excluded fields
    components          : Annotated[List[ComponentConfig], Field(default_factory=list, exclude=True)]
    project_root        : Annotated[str, Field(exclude=True, description="The root folder of the project")] = None
    _components_by_name : dict[str, ComponentConfig] = PrivateAttr(None)

    def get_component(self, name: str):
        if self._components_by_name is None:
            self._components_by_name = {component.name: component for component in self.components}

        component = self._components_by_name.get(name, None)
        if component is None:
            raise ValueError(f"Component '{name}' not found in the project configuration. Available components: {list(self._components_by_name.keys())}")
        return component
