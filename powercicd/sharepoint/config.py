from typing import Literal

from pydantic import Field
from typing_extensions import Annotated

from powercicd.shared.config import ComponentConfig


class SharepointComponentConfig(ComponentConfig):
    type: Annotated[Literal["sharepoint"], Field(description="The type of the component")] = "sharepoint"
