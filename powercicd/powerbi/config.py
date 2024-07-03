import logging
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import Annotated

from powercicd.shared.config import ComponentConfig

_log = logging.getLogger(__name__)

Report = dict
Group = dict
Dataset = dict
Datasource = dict
WeekDays = Literal["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
NotifyOption = Literal["MailOnFailure", "NoNotification"]


class DatasetRefreshSchedule(BaseModel):
    enabled         : Annotated[bool           , Field(description="Whether the refresh schedule is enabled")]
    localTimeZoneId : Annotated[str            , Field(description="The local time zone ID", examples=["UTC", "Romance Standard Time"])]
    days            : Annotated[List[WeekDays] , Field(description="The days of the week when the refresh should occur")]
    times           : Annotated[List[str]      , Field(description="The times of the day when the refresh should occur", examples=["00:00", "12:00"])]
    NotifyOption    : Annotated[NotifyOption   , Field(description="The notification option")]


class PowerBiComponentConfig(ComponentConfig):
    group_name           : Annotated[str                              , Field(description="The name of the group")]
    report_name          : Annotated[str                              , Field(description="The name of the report")]
    type                 : Annotated[Literal["powerbi"]               , Field(description="The type of the component")] = "powerbi"
    refresh_schedule     : Annotated[Optional[DatasetRefreshSchedule] , Field(description="The schedule for the dataset refresh")]
    dataset_parameters   : Annotated[dict[str, Any]                   , Field(description="The parameters for the dataset refresh")]
    powerapps_id_by_name : Annotated[Optional[dict[str, str]]         , Field(description="The PowerApps ID by powerapps name")] = None

