# %%
import logging
import re

import typer
from typing_extensions import Annotated

import powercicd.powerbi.powerbi_utils as powerbi_utils
from powercicd.config import get_project_config
from powercicd.powerbi.config import PowerBiComponentConfig
from powercicd.powerbi.powerbi_client import PowerBiWebClient
from powercicd.shared.config import ProjectConfig

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


main_cli = typer.Typer()
powerbi_cli = typer.Typer()
main_cli.add_typer(powerbi_cli, name="powerbi")


@main_cli.callback(no_args_is_help=True)
def shared_to_all_commands(
    ctx: typer.Context,
    stage : Annotated[str, typer.Option(
        help="The cloud stage to use. this env designation will be used as suffix to find the project and component configuration files"
    )],
    project_dir : Annotated[str, typer.Option(
        help="The project directory to work on",
        prompt=False
    )] = None
):
    ctx.obj = get_project_config(stage, lookup_path=project_dir)
    ctx.ensure_object(ProjectConfig)


@powerbi_cli.command()
def login(
    ctx: typer.Context,
    keep_browser_open: Annotated[bool, typer.Option(
        help="Keep the browser open after deployment (for debugging purposes)",
        prompt=False,
        envvar="KEEP_BROWSER_OPEN"
    )]
):
    project_config: ProjectConfig = ctx.obj
    pbi = PowerBiWebClient(tenant=project_config.tenant, keep_browser_open=keep_browser_open)
    pbi.login_in_browser()
    pbi.close_browser()


@powerbi_cli.command()
def deploy(
    ctx: typer.Context,
    components: Annotated[list[str], typer.Argument(
        help="The component to deploy"
    )] = None,
    deploy_report: Annotated[bool, typer.Option(
        prompt=False, help="Deploy the report",
    )] = True,
    deploy_app: Annotated[bool, typer.Option(
        prompt=False, help="Deploy the report",
    )] = True,
    keep_browser_open: Annotated[bool, typer.Option(
        help="Keep the browser open after deployment (for debugging purposes)",
        prompt=False, envvar="KEEP_BROWSER_OPEN"
    )] = False
):
    if not deploy_report and not deploy_app:
        log.error("Nothing to deploy: neither report nor app is selected. Exiting...")
        return

    project_config: ProjectConfig = ctx.obj
    if components is None:
        component_configs = project_config.components
    else:
        component_configs = [project_config.get_component(component) for component in components]

    pbi = PowerBiWebClient(tenant=project_config.tenant, keep_browser_open=keep_browser_open)

    # first the app login, because it is definitively the most expensive with the browser, and
    # it ensures that the correct browser is active for the api login, where the user has already logged in
    if deploy_app:
        pbi.login_in_browser()
    pbi.login_in_api()

    if deploy_report:
        component_config: PowerBiComponentConfig
        for component_config in component_configs:
            group = pbi.get_group_by_name(component_config.group)
            upload_report_name = f"{component_config.report_name} {project_config.version.resulting_version}"

            tmp_folder = f"{component_config.component_root}/temp/deploy"
            src_code_folder = f"{component_config.component_root}/src"
            pbix_filepath = f"{tmp_folder}/{upload_report_name}.pbix"

            dataset_parameters = component_config.dataset_parameters.copy()
            dataset_parameters["DATASET_VERSION"] = project_config.version.resulting_version

            # convert src code to pbix
            powerbi_utils.convert_src_code_to_pbix(
                src_code_folder=src_code_folder,
                pbix_filepath=pbix_filepath,
                temp_folder=tmp_folder,
                powerapps_id_by_name=component_config.powerapps_id_by_name,
                version=project_config.version.resulting_version,
            )

            # deploy report
            log.info(f"Deploying report '{upload_report_name}' to group '{group['Name']}'")
            pbi.deploy_report(
                group_id=group["Id"],
                upload_report_name=upload_report_name,
                final_report_name=component_config.report_name,
                pbix_file_path=pbix_filepath,
                dataset_parameters=dataset_parameters,
                refresh_schedule=component_config.refresh_schedule,
                cleanup_regex=rf"{re.escape(upload_report_name)}.+"
            )

    if deploy_app:
        group_names = sorted(set(component_config.name for component_config in component_configs))
        for group_name in group_names:
            group = pbi.get_group_by_name(group_name)
            log.info(f"Deploying app for group '{group_name}'")
            pbi.deploy_app(group["Id"])
        log.info("All apps deployed")
        pbi.close_browser()


@powerbi_cli.command("import")
def import_from_pbix(
    ctx: typer.Context,
    component: Annotated[str, typer.Argument(
        help="The component to import to"
    )],
    pbix_file: Annotated[str, typer.Argument(
        help="The pbix file to import from"
    )]
):
    project_config   : ProjectConfig = ctx.obj
    component_config = project_config.get_component(component)
    src_code_folder  = component_config.component_root
    tmp_folder       = f"{src_code_folder}/temp/import_from_pbix"
    powerbi_utils.convert_pbix_to_src_code(pbix_file, src_code_folder, tmp_folder)


@powerbi_cli.command("export")
def export_to_pbix(
    ctx: typer.Context,
    component: Annotated[str, typer.Argument(
        help="The component to import to"
    )],
    pbix_file: Annotated[str, typer.Argument(
        help="The pbix file to export to"
    )]
):
    project_config   : ProjectConfig = ctx.obj
    component_config = project_config.get_component(component)
    src_code_folder  = component_config.component_root
    tmp_folder       = f"{src_code_folder}/temp/export_to_pbix"

    powerbi_utils.convert_src_code_to_pbix(
        pbix_file,
        src_code_folder,
        component_config.name,
        component_config.parent_project.version.resulting_version,
        tmp_folder
    )


if __name__ == '__main__':
    try:
        main_cli()
    except typer.BadParameter as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)