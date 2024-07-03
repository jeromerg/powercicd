import json

from powercicd.config import AllComponentsDeserializer
from powercicd.shared.config import ProjectConfig
import os

os.makedirs("schemas", exist_ok=True)

with open("schemas/project_config.jsonschema.json", "w") as f:
    f.write(ProjectConfig.schema_json(indent=2))

with open("schemas/component_config.jsonschema.json", "w") as f:
    containing_json_schema = AllComponentsDeserializer.model_json_schema()
    json_schema = {
        "$defs": containing_json_schema["$defs"],
        ** containing_json_schema["properties"]["component"]

    }
    f.write(json.dumps(json_schema, indent=2))
