import logging
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from powercicd.shared.config import ComponentConfig

_log = logging.getLogger(__name__)

Report = dict
Group = dict
Dataset = dict
Datasource = dict
WeekDays = Literal["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
NotifyOption = Literal["MailOnFailure", "NoNotification"]


class DatasetRefreshSchedule(BaseModel):
    enabled         : bool         = Field(..., description="Whether the refresh schedule is enabled")
    localTimeZoneId : str          = Field(..., description="The local time zone ID", examples=["UTC", "Romance Standard Time"])
    days            : WeekDays     = Field(..., description="The days of the week when the refresh should occur")
    times           : List[str]    = Field(..., description="The times of the day when the refresh should occur", examples=["00:00", "12:00"])
    NotifyOption    : NotifyOption = Field(..., description="The notification option")


class PowerBIComponentConfig(ComponentConfig):
    type                 : Literal["powerbi"]               = "powerbi"
    schedule             : Optional[DatasetRefreshSchedule] = Field(..., description="The schedule for the dataset refresh")
    dataset_parameters   : dict[str, Any]                   = Field(..., description="The parameters for the dataset refresh")
    powerapps_id_by_name : Optional[dict[str, str]]         = Field(None, description="The PowerApps ID by powerapps name")

