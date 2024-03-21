import glob
import yaml
import os
from typing import Any, Union
import logging

from pydantic import BaseModel, Field

from powercicd.powerbi.config import PowerBIComponentConfig
from powercicd.powerbi.file_utils import find_parent_dir_where_exists_file
from powercicd.shared.config import ProjectConfig, ComponentConfig
from powercicd.sharepoint.config import SharepointComponentConfig
from powercicd.powerapps.config import PowerAppsComponentConfig


AnyComponent = Union[PowerBIComponentConfig, PowerAppsComponentConfig, SharepointComponentConfig]


PROJECT_CONFIG_FILENAME_FMT   : str = "power-project-{env}.yaml"
COMPONENT_CONFIG_FILENAME_FMT : str = "power-component-{env}.yaml"


log = logging.getLogger(__name__)


class AllComponentsDeserializer(BaseModel):
    component: AnyComponent = Field(..., description="The component to deserialize", discriminator="type")

    @classmethod
    def deserialize_file(cls, component_config_file: Any) -> AnyComponent:
        log.info(f"Reading component config from '{component_config_file}'")
        with open(component_config_file, 'r', encoding='utf-8') as f:
            component_config_json = yaml.safe_load(f)
        return cls.model_validate(component_config_json).component


def get_current_version(project_root, project_config):
    major_version = project_config["version"]["major"]
    minor_version = project_config["version"]["minor"]
    build_ground  = project_config["version"]["build_ground"]

    count_commits = int(os.popen(f"git -C {project_root} rev-list HEAD --count").read().strip())
    are_changes = os.popen(f"git -C {project_root} status --porcelain").read().strip() != ""
    build_number = count_commits - build_ground
    if are_changes:
        version = f"{major_version}.{minor_version}.{build_number}M"
    else:
        version = f"{major_version}.{minor_version}.{build_number}"
    log.info(f"Version: {version}")
    return version


def get_project_config(stage: str, lookup_path: str = None) -> ProjectConfig:
    project_config_filename = PROJECT_CONFIG_FILENAME_FMT.format(env=stage)
    component_config_filename = COMPONENT_CONFIG_FILENAME_FMT.format(env=stage)

    if lookup_path is None:
        lookup_path = os.getcwd()

    # Determine project root and project_config.json
    project_root = find_parent_dir_where_exists_file(lookup_path, project_config_filename)
    log.info(f"Project root: {project_root}")

    # Load project_config.json
    with open(os.path.join(project_root, project_config_filename), 'r', encoding='utf-8') as f:
        project_json_config = yaml.safe_load(f)

    project_config = ProjectConfig(**project_json_config)

    # Enrich project_config
    project_config.project_root = project_root
    project_config.version.resulting_version = get_current_version(project_root, project_config)

    # load component configs
    project_config["components"] = []
    component_config_files = [f for f in glob.glob(f"{project_root}/{component_config_filename}")]
    for component_config_file in component_config_files:
        log.info(f"Reading component config from '{component_config_file}'")
        component_config = AllComponentsDeserializer.deserialize_file(component_config_file)
        component_config.parent_project = project_config
        project_config.components.append(component_config)

    return project_config


def get_component_config(stage: str, lookup_path: str = None) -> ComponentConfig:
    project_config_filename = PROJECT_CONFIG_FILENAME_FMT.format(env=stage)
    component_config_filename = COMPONENT_CONFIG_FILENAME_FMT.format(env=stage)

    if lookup_path is None:
        lookup_path = os.getcwd()

    component_dir = find_parent_dir_where_exists_file(lookup_path, component_config_filename)
    project_dir   = os.path.dirname(component_dir)
    # verify if PROJECT_CONFIG_FILENAME exists in the same folder
    if not os.path.exists(f"{project_dir}/{project_config_filename}"):
        raise ValueError(f"{project_config_filename} not found in the folder '{project_dir}' (parent directory of component folder '{component_dir}')")
    name = os.path.relpath(component_dir, project_dir)
    project_config = get_project_config(component_dir)
    return project_config.get_component(name)
