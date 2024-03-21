from typing import Literal

from powercicd.shared.config import ComponentConfig


class SharepointComponentConfig(ComponentConfig):
    type: Literal["sharepoint"] = "sharepoint"
