from typing import Literal

from powercicd.shared.shared_config import ComponentConfig


class PowerAppsComponentConfig(ComponentConfig):
    type: Literal["powerapps"] = "powerapps"
