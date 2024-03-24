# %%
import gzip
import logging
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

import requests
from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential
from requests.sessions import Session
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chromium.webdriver import ChromiumDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from powercicd.powerbi.config import DatasetRefreshSchedule, Report, Group, Datasource
from powercicd.shared.logging_utils import log_call
from powercicd.shared.selenium_common import new_browser

# %%
log = logging.getLogger(__name__)


# TODO: Migrate whole retrieve and deploy scripts to python by using example: https://github.com/Azure-Samples/powerbi-powershell/blob/master/manageRefresh.ps1


def build_datasource_key(ds) -> str:
    return "_".join([ds[key].strip(" /") for key in sorted(ds) if isinstance(ds[key], str)])


class PowerBiWebClient:
    def __init__(self, tenant: str, keep_browser_open: bool):
        self.keep_browser_open : bool                   = keep_browser_open
        self.tenant            : str                    = tenant
        self.powerbi_url       : str                    = f"https://app.powerbi.com/home?ctid={self.tenant}&experience=power-bi"
        self._browser          : None | ChromiumDriver  = None
        self._azure_credential : DefaultAzureCredential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        self._token            : None | AccessToken     = None
        self._session          : None | Session         = None

        self.active_refresh_timeout_seconds = 60 * 60 * 20
        self.active_refresh_polling_seconds = 60

    @property 
    def browser(self) -> ChromiumDriver:
        if self._browser is None:
            self._browser = new_browser(self.tenant, self.keep_browser_open)
        return self._browser

    def close_browser(self):
        if self.keep_browser_open:
            return
            
        if self._browser is not None:
            log.info("Closing the browser...")
            self._browser.quit()
            self._browser = None
        else:
            log.info("No browser to close.")
        
    @property
    def wait_browser(self) -> WebDriverWait:
        return WebDriverWait(self.browser, 10)

    def _has_token_expired(self):
        return self._token is None or self._token.expires_on < time.time() + 60

    @property
    def token_string(self):
        if self._has_token_expired():
            self._token: AccessToken = self._azure_credential.get_token("https://analysis.windows.net/powerbi/api/.default")
        return self._token.token

    @property
    def session(self):
        if self._has_token_expired():
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.token_string}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
        return self._session

    def login_in_api(self):
        dummy = self.token_string
        log.info("Logged in to Power BI API")

    def is_logged_in_in_browser(self):
        log.info("Verifying login to Power BI")

        log.info(f"Opening the Power BI tenant site: '{self.powerbi_url}'")
        self.browser.get(self.powerbi_url)
        
        log.info("Analyzing the page...")
        try:
            _ = self.wait_browser.until(EC.element_to_be_clickable((By.CLASS_NAME, "userInfoButton")))
            log.info("Logged in!")
            return True
        except TimeoutException:
            log.info("Not logged in.")
            return False
        
    def login_in_browser(self):
        if self.is_logged_in_in_browser():
            return

        print("-------------------------------------------------------------------------------")
        input("Please login manually in the opened browser window and press Enter to continue.")
        
        if not self.is_logged_in_in_browser():
            raise ValueError("Login check failed even after manual login. Please check the opened browser window.")

    @log_call()
    def try_get_group_by_name(self, group_name: str) -> Group | None:
        groups: list[Group] = self.session.get("https://api.powerbi.com/v1.0/myorg/groups").json()["value"]
        groups = [g for g in groups if g["Name"] == group_name]
        if len(groups) == 0:
            return None
        elif len(groups) > 1:
            raise ValueError(f"Multiple groups with the same name '{group_name}' found... You must delete the duplicates.")
        return groups[0]

    def get_group_by_name(self, group_name: str) -> Group:
        group = self.try_get_group_by_name(group_name)
        if group is None:
            raise ValueError(f"Group '{group_name}' not found")
        return group

    @log_call()
    def try_get_report_by_name(self, group_id: str, report_name: str) -> Report | None:
        reports: list[Report] = self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports").json()["value"]
        reports = [ri for ri in reports if ri["Name"] == report_name]
        if len(reports) == 0:
            return None
        elif len(reports) > 1:
            raise ValueError(f"Multiple reports with the same name '{report_name}' found in group '{group_id}'... You must delete the duplicates.")
        return reports[0]

    def get_report_by_name(self, group_id: str, report_name: str) -> Report:
        report = self.try_get_report_by_name(group_id, report_name)
        if report is None:
            raise ValueError(f"Report '{report_name}' not found in group '{group_id}'")
        return report

    @log_call()
    def wait_for_end_of_any_active_dataset_refresh(self, group_id: str, dataset_id: str):
        start_monotonic = time.monotonic()
        while True:
            if time.monotonic() - start_monotonic > self.active_refresh_timeout_seconds:
                raise TimeoutError("Waiting for the end of any active dataset refresh took too long.")

            refreshes = self.session.get(f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/refreshes").json()["value"]
            refreshes_in_status_unknown = [r for r in refreshes if r.status == "Unknown"]
            if len(refreshes_in_status_unknown) == 0:
                log.info("No active refreshes.")
                break
            log.info(f"{len(refreshes_in_status_unknown)} Active refreshes... sleep {self.active_refresh_polling_seconds} seconds")
            time.sleep(self.active_refresh_polling_seconds)

    @log_call()
    def get_dataset(self, group_id, dataset_id):
        return self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}").json()["value"]

    @log_call()
    def retrieve_report(self, group_id: str, report_id: str, file_path: str):
        log.info(f"Downloading the report: '{report_id}' to '{file_path}'")
        file_dir  = Path(file_path).parent
        file_name = Path(file_path).name
        file_dir.mkdir(parents=True, exist_ok=True)
        request = Request(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}/Export", method="GET")
        with (
            urlopen(request) as response,
            gzip.GzipFile(fileobj=response, mode='rb') as uncompressed,
            open(file_path, "wb") as out_file
        ):
            while True:
                chunk = uncompressed.read(1024 * 1024)
                if not chunk:
                    break
                log.info(f"Writing {len(chunk)} bytes to '{file_path}'")
                out_file.write(chunk)

    @log_call()
    def take_over_report(self, group_id: str, report_id: str):
        log.info(f"Taking over the report: '{report_id}'")
        self.session.post(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}/Default.TakeOver")

    @log_call()
    def update_dataset_parameters(self, group_id: str, dataset_id: str, dataset_parameters: dict[str, str]):
        body = {
            "updateDetails": [
                {
                    "name": key,
                    "newValue": value
                }
                for key, value
                in dataset_parameters.items()
            ]
        }
        self.session.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/Default.UpdateParameters",
            json=body
        )

    @log_call()
    def import_report(
        self,
        group_id: str,
        report_name: str,
        file_path: str,
    ):
        with open(file_path, "rb") as f:
            req = Request(
                f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/imports?datasetDisplayName={report_name}&nameConflict=CreateOrOverwrite",
                f,
                headers=self.session.headers,
                method="POST"
            )
            req.add_header("Content-Type", "multipart/form-data")
            req.add_header("Content-Disposition", f"attachment; filename={file_path}")
            urlopen(req)

    @log_call()
    def get_gateway_cluster_datasources(self, gateway_type: str | None = None) -> list[Datasource]:
        all_datasources = self.session.get("https://api.powerbi.com/v2.0/myorg/me/gatewayClusterDatasources?$expand=users").json()["value"]
        if gateway_type is None:
            return all_datasources
        else:
            return [s for s in all_datasources if s["GatewayType"] == gateway_type]

    @log_call()
    def get_dataset_datasources(self, group_id: str, dataset_id: str) -> list[Datasource]:
        return self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/datasources").json()["value"]

    @log_call()
    def bind_dataset_to_gateway(self, group_id: str, dataset_id: str, gateway_id: str, datasource_ids: list[str]):
        body = {
            "gatewayObjectId": gateway_id,
            "datasourceObjectIds": datasource_ids
        }
        self.session.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/Default.BindToGateway",
            json=body
        )

    @log_call()
    def set_dataset_refresh_schedule(self, group_id: str, dataset_id: str, refresh_schedule: DatasetRefreshSchedule):
        body = {
            "value": refresh_schedule.dict()
        }
        self.session.patch(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/refreshSchedule",
            json=body
        )

    @log_call()
    def update_report_content(self, group_id: str, upload_report_id: str, final_report_id: str):
        body = {
            "sourceReport": {
                "sourceReportId" : upload_report_id,
                "sourceWorkspaceId" : group_id,
            },
            "sourceType": "ExistingReport",
        }

        self.session.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{final_report_id}/Default.UpdateContent",
            json=body
        )

    @log_call()
    def rebind_report_to_dataset(self, group_id: str, report_id: str, dataset_id: str):
        body = {
            "datasetId": dataset_id
        }
        self.session.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}/Rebind",
            json=body
        )

    @log_call()
    def clone_report(self, group_id: str, report_id: str, final_report_name: str):
        body = {
            "name": final_report_name
        }
        self.session.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}/Clone",
            json=body
        )

    @log_call()
    def deploy_app(self, group_id: str, log_dir: str):
        try:
            # %%
            group_url = f"https://app.powerbi.com/groups/{group_id}/list?ctid={self.tenant}&experience=power-bi"
            log.info(f"Opening the group: '{group_url}'")
            self.browser.get(group_url)

            # %%
            log.info("Waiting for the update app button in group view to appear...")
            update_button = self.wait_browser.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='update-app']")))
            update_button.click()

            # %%
            log.info("Waiting for the update app button in update dialog to appear...")
            update_app_publish_button = self.wait_browser.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='update-app-publish']")))
            # check if the button is enabled
            if not update_app_publish_button.is_enabled():
                screenshot_path = f"{log_dir}/disabled_update_screenshot.png"
                self.browser.save_screenshot(screenshot_path)
                log.warning(
                    f"The 'Update app' button is disabled. You need to deploy manually to (re-)configure the app!" 
                    f"\n  --> URL '{self.browser.current_url}'. \n --> Screen shot saved to '{screenshot_path}'"
                )
                return
            log.info("Publishing the app... ('Update app' button is enabled)")
            update_app_publish_button.click()

            # %%
            ok_button = self.wait_browser.until(EC.element_to_be_clickable((By.ID, "okButton")))
            ok_button.click()

            # %%
            input_publish_url = self.wait_browser.until(EC.presence_of_element_located((By.ID, "app-publish-url")))
            publish_url = input_publish_url.get_attribute("value")
            log.info(f"!!!! Published app URL: {publish_url}")
        except:
            screenshot_path = f"{log_dir}/error_screenshot.png"
            self.browser.save_screenshot(screenshot_path)
            log.exception("Failed to deploy the app. Screen shot saved to '{screenshot_path}'")
            raise

    @log_call()
    def cleanup_reports(self, group_id: str, cleanup_regex: str, exclude_report_names: list[str]):
        exclude_report_names = set(exclude_report_names)

        re_cleanup = re.compile(cleanup_regex)

        reports = self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports").json()["value"]
        reports_to_delete = [r for r in reports if re_cleanup.match(r["Name"]) and r["Name"] not in exclude_report_names]
        for report in reports_to_delete:
            report_id = report["Id"]
            try:
                log.info(f"Deleting report '{report['Name']}' with id '{report_id}'")
                self.session.delete(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}")
                log.info(f"Report deleted successfully.")
            except:
                log.exception(f"Failed to delete report '{report['Name']}'")

        reports = self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports").json()["value"]
        reports_dataset_ids = set(r["DatasetId"] for r in reports)
        datasets = self.session.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets").json()["value"]
        datasets_to_delete = [d for d in datasets if d["Id"] not in reports_dataset_ids]
        for dataset in datasets_to_delete:
            dataset_id = dataset["Id"]
            try:
                log.info(f"Deleting dataset '{dataset['Name']}' with id '{dataset_id}'")
                self.session.delete(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}")
                log.info(f"Dataset deleted successfully.")
            except:
                log.exception(f"Failed to delete dataset '{dataset['Name']}'")

    @log_call()
    def deploy_report(
        self,
        group_id: str,
        upload_report_name: str,
        final_report_name: str,
        file_path: str,
        dataset_parameters: dict[str, str] = None,
        refresh_schedule: DatasetRefreshSchedule | None = None,
        cleanup_regex: str | None = None,
    ):
        report_before = self.try_get_report_by_name(group_id, upload_report_name)

        if report_before is not None:
            log.warning(f"Report '{upload_report_name}' already exists in the group '{group_id}'. Report and underlying semantic model may be temporarily out-of-sync!!")
            self.take_over_report(group_id, report_before["Id"])

        self.import_report(group_id, upload_report_name, file_path)

        report       = self.try_get_report_by_name(group_id, upload_report_name)
        report_id    = report["Id"]
        dataset_id   = report["DatasetId"]
        dataset      = self.get_dataset(group_id, dataset_id)

        self.take_over_report(group_id, report_id)
        self.wait_for_end_of_any_active_dataset_refresh(group_id, dataset_id)
        if dataset_parameters is not None:
            self.update_dataset_parameters(dataset, dataset_parameters)

        # identify managed datasources to bind to the gateway cluster datasources
        tenant_datasources               = self.get_gateway_cluster_datasources("TenantCloud")
        dataset_datasources              = self.get_dataset_datasources(group_id, dataset_id)
        tenant_datasources_by_key        = { build_datasource_key(ds) : ds for ds in tenant_datasources }
        datasources_by_key               = { build_datasource_key(ds) : ds for ds in dataset_datasources }
        unmanaged_datasource_keys        = sorted(set(datasources_by_key.keys()) - set(tenant_datasources_by_key.keys()))
        managed_datasource_keys          = sorted(set(datasources_by_key.keys()) & set(tenant_datasources_by_key.keys()))
        managed_datasource_by_gateway_id = {
            tenant_datasources_by_key[key]["ClusterId"] : tenant_datasources_by_key[key]
            for key
            in managed_datasource_keys
        }
        log.info(f"{unmanaged_datasource_keys=}, {managed_datasource_keys=}")

        # bind datasource to relevant gateway datasources
        for gateway_id, dataset_datasources in managed_datasource_by_gateway_id.items():
            tenant_datasource_ids = [ds["Id"] for ds in dataset_datasources]
            self.bind_dataset_to_gateway(group_id, dataset_id, gateway_id, tenant_datasource_ids)

        # trigger dataset refresh
        self.wait_for_end_of_any_active_dataset_refresh(group_id, dataset_id)
        self.session.post(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/refreshes")
        self.wait_for_end_of_any_active_dataset_refresh(group_id, dataset_id)

        # set refresh schedule
        if refresh_schedule is not None:
            self.set_dataset_refresh_schedule(group_id, dataset_id, refresh_schedule)

        # finalize the report
        final_report = self.try_get_report_by_name(group_id, final_report_name)
        if final_report is not None:
            final_report_id = final_report["Id"]
            final_report_dataset_id = final_report["DatasetId"]
            self.take_over_report(group_id, final_report_id)
            self.wait_for_end_of_any_active_dataset_refresh(group_id, final_report_dataset_id)
            self.update_report_content(group_id, final_report_id, report_id)
            self.rebind_report_to_dataset(group_id, final_report_id, dataset_id)
        else:
            self.clone_report(group_id, report_id, final_report_name)
            final_report = self.try_get_report_by_name(group_id, final_report_name)
            final_report_id = final_report["id"]
            final_report_dataset_id = final_report["datasetId"]

        # cleanup
        if cleanup_regex is not None:
            self.cleanup_reports(group_id, cleanup_regex, exclude_report_names=[final_report_name])
