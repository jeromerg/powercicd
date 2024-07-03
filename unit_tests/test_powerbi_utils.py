import json
import os
import shutil
import zipfile

import pytest

from powercicd.powerbi.powerbi_utils import convert_pbix_to_src_code, convert_src_code_to_pbix
from jsonpath_ng.ext import parse

THIS_FILE_DIR = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))


@pytest.fixture
def tmp_dir(request):
    r = f"{THIS_FILE_DIR}/tmp/{request.node.name}"
    if os.path.exists(r):
        shutil.rmtree(r)
    os.makedirs(r, exist_ok=True)
    try:
        yield r
    except:
        pass
    # else:
    #     os.removedirs(r)


def test_convert_pbix_to_src_code(tmp_dir):
    pbix_file = f"{THIS_FILE_DIR}/test_samples/test_report.pbix"
    src_folder = f"{tmp_dir}/src_dir"
    tmp_folder = f"{tmp_dir}/tmp_dir"
    convert_pbix_to_src_code(pbix_file, src_folder, tmp_folder)

    assert not os.path.exists(f"{src_folder}/Report/Layout")
    assert os.path.exists(f"{src_folder}/Report/Layout.json")
    with open(f"{src_folder}/Report/Layout.json") as f:
        layout = json.load(f)

    expected_version_matches = [m for m in parse("$..value").find(layout) if m.value == "REPORT_VERSION_REMOVED_BY_BUILD_SCRIPT"]
    assert len(expected_version_matches) == 1

    expected_powerapps_id_matches = [m for m in parse("$..Value").find(layout) if m.value == "POWERAPPS_APP_ID_REMOVED_BY_BUILD_SCRIPT"]
    assert len(expected_powerapps_id_matches) == 1


def test_convert_src_code_to_pbix(tmp_dir):
    pbix_file = f"{tmp_dir}/test_report.pbix"
    src_folder = f"{THIS_FILE_DIR}/test_samples/test_report"
    tmp_folder = f"{tmp_dir}/tmp_dir"
    powerapps_id_by_name = {
        "my_powerapps_app": "b944ef36-81f7-482c-a6d6-f29c9f89eabc"
    }
    version = "the build will replace this content by the report version"
    convert_src_code_to_pbix(src_folder, pbix_file, tmp_folder, powerapps_id_by_name, version)

    # unzip the pbix file
    with zipfile.ZipFile(pbix_file, 'r') as zip_ref:
        zip_ref.extractall(f"{tmp_dir}/pbix_content_unzipped_to_verify")

    # check the content of the pbix file
    assert not os.path.exists(f"{tmp_dir}/pbix_content_unzipped_to_verify/Report/Layout.json")
    assert os.path.exists(f"{tmp_dir}/pbix_content_unzipped_to_verify/Report/Layout")
    with open(f"{tmp_dir}/pbix_content_unzipped_to_verify/Report/Layout", 'r', encoding='utf-16 le') as f:
        content = f.read()

    assert "the build will replace this content by the report version" in content
    assert "'/providers/Microsoft.PowerApps/apps/b944ef36-81f7-482c-a6d6-f29c9f89eabc'" in content
