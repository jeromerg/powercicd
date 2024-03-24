from typing import Literal

from pydantic import Field
from typing_extensions import Annotated

from powercicd.shared.config import ComponentConfig


class PowerAppsComponentConfig(ComponentConfig):
    type: Annotated[Literal["powerapps"], Field(description="The type of the component")] = "powerapps"
