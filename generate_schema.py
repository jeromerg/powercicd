from powercicd.config import AllComponentsDeserializer
from powercicd.shared.config import ProjectConfig
import os

os.makedirs("schemas", exist_ok=True)

with open("schemas/project_config.jsonschema.json", "w") as f:
    f.write(ProjectConfig.schema_json(indent=2))

with open("schemas/component_config.jsonschema.json", "w") as f:
    f.write(AllComponentsDeserializer.schema_json(indent=2))
