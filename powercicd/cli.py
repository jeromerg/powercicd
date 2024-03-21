# %%
import json
import logging

import click
from powercicd.powerbi.powerbi_client import PowerBiWebClient
from powercicd.config import get_project_config, get_component_config
from powercicd.shared.selenium_common import configure_selenium_logger
import powercicd.powerbi.powerbi_utils as powerbi_utils

logging.basicConfig(level=logging.INFO)
configure_selenium_logger()
log = logging.getLogger(__name__)

@click.group()
@click.option('--stage', required=True, prompt=True, help="The cloud stage to use. this env designation will be used as suffix to find the project and component configuration files")
@click.option('--project-dir', required=False, default=None, prompt=False, help="The project directory to work on")
@click.option('--component-name', required=False, default=None, prompt=False, help="The component name to work on")
@click.pass_context
def cli(ctx, stage: str, project_dir: str|None, component_name: str|None):
    ctx.ensure_object(dict)
    ctx.obj['project_dir'] = project_dir
    ctx.obj['component_name'] = component_name
    ctx.obj['stage'] = stage


@cli.command()
@click.option('--keep-browser-open', required=False, default=False, help="Keep the browser open after deployment", prompt=False, envvar="KEEP_BROWSER_OPEN")
def login(ctx, keep_browser_open: bool):
    project_config = get_project_config(ctx.obj['project_dir'])
    pbi = PowerBiWebClient(tenant=project_config.tenant, keep_browser_open=keep_browser_open)
    pbi.login_if_required()
    pbi.close_browser()


@cli.command()
@click.option('--workspace', required=True, help="Workspace ID", prompt=True)
@click.option('--keep-browser-open', required=False, default=False, help="Keep the browser open after deployment", prompt=False, envvar="KEEP_BROWSER_OPEN")
@click.pass_context
def deploy_app(ctx, workspace: str, keep_browser_open: bool):
    project_config = get_project_config(ctx.obj['project_dir'])
    pbi = PowerBiWebClient(tenant=project_config.tenant, keep_browser_open=keep_browser_open)
    pbi.deploy_app(workspace_id=workspace)
    pbi.close_browser()


@cli.command()
@click.pass_context
@click.option('--pbix-file', required=True, help="The pbix file to import from", prompt=True)
def import_from_pbix(ctx, pbix_file: str):
    component_config = get_component_config(ctx.obj['component_name'])
    src_code_folder  = component_config.component_root
    tmp_folder       = f"{src_code_folder}/temp/import_from_pbix"
    powerbi_utils.convert_pbix_to_src_code(pbix_file, src_code_folder, tmp_folder)


@cli.command()
@click.pass_context
@click.option('--pbix-file', required=True, help="The pbix file to export to", prompt=True)
def export_to_pbix(ctx, pbix_file: str):
    component_config = get_component_config(ctx.obj['component_name'])
    src_code_folder  = component_config.component_root
    tmp_folder       = f"{src_code_folder}/temp/import_from_pbix"

    # Remark: Current hack: improve by search directly the powerapps id from "depends_on fields" and the powerapps REST API
    with open(f"{component_config.parent_project.project_root}/powerapps/powerapps_by_stage.json", 'r', encoding='utf-8') as f:
        powerapps_id_by_name = json.load(f)

    powerbi_utils.convert_src_code_to_pbix(
        pbix_file,
        src_code_folder,
        powerapps_id_by_name,
        component_config.parent_project.version.resulting_version,
        tmp_folder
    )

if __name__ == '__main__':
    cli()