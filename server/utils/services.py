import re
import pathlib
import yaml
from server.utils.common import ResourcesManager


class ServicesManager(ResourcesManager):
    @staticmethod
    def get_vars_from_tfvars(file_path: str):
        with open(file_path, "r") as f:
            content = f.read()
            variables = re.findall(r"(^.+?)\s*=", content, re.MULTILINE)

        return variables

    @staticmethod
    def get_service_vars(service_dir_path: str):
        with open(service_dir_path.replace("file://", ""), 'r') as stream:
            try:
                yaml_obj = yaml.load(stream, Loader=yaml.FullLoader)
                doc_type = yaml_obj.get('kind', '')
            except yaml.YAMLError as exc:
                return []

        if doc_type == "TerraForm":
            tfvars = []
            files = pathlib.Path(service_dir_path.replace("file://", "")).parent.glob("./*")
            for file in files:
                if file.name.endswith('.tfvars'):
                    item = {
                        "file": pathlib.Path(file).name,
                        "variables": ServicesManager.get_vars_from_tfvars(file)
                    }
                    tfvars.append(item)

            return tfvars

        return []
