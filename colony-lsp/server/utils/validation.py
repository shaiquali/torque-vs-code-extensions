import os
import re
from typing import List
from pygls.lsp.types import diagnostics
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from server.ats.tree import BlueprintTree
from server.constants import PREDEFINED_COLONY_INPUTS
from server.utils import applications, services


class ValidationHandler:
    def __init__(self, tree: BlueprintTree, root_path: str):
        self._tree = tree
        self._diagnostics = []
        self._root_path = root_path

    def _add_diagnostic(
            self,
            start_position: Position,
            end_position: Position,
            message: str = "",
            diag_severity: DiagnosticSeverity = None):
        self._diagnostics.append(
            Diagnostic(
                range=Range(
                    start=start_position,
                    end=end_position
                ),
                message=message,
                severity=diag_severity
            ))
    
    # TODO: add validation method which will be common for all trees for finding
    # duplicates in inputs

    def validate(self):
        pass


class AppValidationHandler(ValidationHandler):
    pass


class BlueprintValidationHandler(ValidationHandler):
    def __init__(self, tree: BlueprintTree, root_path: str):
        super().__init__(tree, root_path)
        self.blueprint_apps = [app.id.text for app in self._tree.apps_node.items] if self._tree.apps_node else []
        self.blueprint_services = [srv.id.text for srv in self._tree.services_node.items] if self._tree.services_node else []

    def _validate_dependency_exists(self):
        message = "The application/service '{}' is not defined in the applications/services section"            
        apps = self.blueprint_apps
        srvs = self.blueprint_services
        apps_n_srvs = set(apps + srvs)

        if self._tree.apps_node:
            for app in self._tree.apps_node.items:
                for dep in app.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(
                            Position(line=dep.start[0], character=dep.start[1]),
                            Position(line=dep.end[0], character=dep.end[1]),
                            message=message.format(dep.text)
                        )
                    elif dep.text == app.id.text:
                        self._add_diagnostic(
                            Position(line=dep.start[0], character=dep.start[1]),
                            Position(line=dep.end[0], character=dep.end[1]),
                            message=f"The app '{app.id.text}' cannot be dependent of itself"
                        )
        if self._tree.services_node:
            for srv in self._tree.services_node.items:
                for dep in srv.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(
                            Position(line=dep.start[0], character=dep.start[1]),
                            Position(line=dep.end[0], character=dep.end[1]),
                            message=message.format(dep.text)
                        )
                    elif dep.text == srv.id.text:
                        self._add_diagnostic(
                            Position(line=dep.start[0], character=dep.start[1]),
                            Position(line=dep.end[0], character=dep.end[1]),
                            message=f"The service '{srv.id.text}' cannot be dependent of itself"
                        )

    def _validate_non_existing_app_is_used(self):
        message = "The app '{}' could not be found in the /applications folder"
        available_apps = applications.get_available_applications_names()
        for app in self._tree.apps_node.items:
            if app.id.text not in available_apps:
                self._add_diagnostic(
                    Position(line=app.id.start[0], character=app.start[1]),
                    Position(line=app.id.end[0], character=app.id.end[1]),
                    message=message.format(app.id.text)
                )

    def _validate_non_existing_service_is_used(self):
        message = "The service '{}' could not be found in the /services folder"
        available_srvs = services.get_available_services_names()
        for srv in self._tree.services_node.items:
            if srv.id.text not in available_srvs:
                self._add_diagnostic(
                    Position(line=srv.id.start[0], character=srv.start[1]),
                    Position(line=srv.id.end[0], character=srv.id.end[1]),
                    message=message.format(srv.id.text)
                )

    def _check_for_unused_blueprint_inputs(self):
        used_vars = set()
        for app in self._tree.apps_node.items:
            used_vars.update({var.value.text.replace("$", "") for var in app.inputs_node.inputs})

        message = "Unused variable {}"

        for input in self._tree.inputs_node.inputs:
            if input.key.text not in used_vars:
                self._add_diagnostic(
                    Position(line=input.key.start[0], character=input.key.start[1]),
                    Position(line=input.key.end[0], character=input.key.end[1]),
                    message=message.format(input.key.text),
                    diag_severity=DiagnosticSeverity.Warning
                )

    def _is_valid_auto_var(self, var_name):
        if var_name.lower() in PREDEFINED_COLONY_INPUTS:
            return True, ""

        parts = var_name.split('.')
        if not parts[0].lower() == "$colony":
            return False, f"{var_name} is not a valid colony-generated variable"

        if not parts[1].lower() == "applications" and not parts[1].lower() == "services":
            return False, f"{var_name} is not a valid colony-generated variable"

        if len(parts) == 4:
            if not parts[3] == "dns":
                return False, f"{var_name} is not a valid colony-generated variable"
            else:
                return True, ""

        if len(parts) == 5:
            if parts[1].lower() == "applications" and (not parts[3].lower() == "outputs" and
                                                       not parts[3].lower() == "dns"):
                return False, f"{var_name} is not a valid colony-generated variable"

            if parts[1].lower() == "services" and not parts[3].lower() == "outputs":
                return False, f"{var_name} is not a valid colony-generated variable"

            if parts[1] == "applications":
                apps = self.blueprint_apps
                if not parts[2] in apps:
                    return False, f"{var_name} is not a valid colony-generated variable (no such app in the blueprint)"
                
                # TODO: check that the app is in the depends_on section

                app_outputs = applications.get_app_outputs(app_name=parts[2])
                if parts[4] not in app_outputs:
                    return False, f"{var_name} is not a valid colony-generated variable ('{parts[2]}' does not have the output '{parts[4]}')"

            if parts[1] == "services":
                srvs = self.blueprint_services
                if not parts[2] in srvs:
                    return False, f"{var_name} is not a valid colony-generated variable (no such service in the blueprint)"

                # TODO: check that the service is in the depends_on section
                
                srv_outputs = services.get_service_outputs(srv_name=parts[2])
                if parts[4] not in srv_outputs:
                    return False, f"{var_name} is not a valid colony-generated variable ('{parts[2]}' does not have the output '{parts[4]}')"

            
        else:
            return False, f"{var_name} is not a valid colony-generated variable (too many parts)"

        return True, ""

    def _validate_var_being_used_is_defined(self):
        bp_inputs = {input.key.text for input in self._tree.inputs_node.inputs}
        message = "Variable '{}' is not defined"
        regex = re.compile('(^\$.+?$|\$\{.+?\})')
        for app in self._tree.apps_node.items:
            for input in app.inputs_node.inputs:
                # we need to check values starting with '$' 
                # and they shouldnt be colony related

                # need to break value to parts to handle variables in {} like: 
                # abcd/${some_var}/asfsd/${var2}
                # and highlight these portions      
                iterator = regex.finditer(input.value.text)
                for match in iterator:
                    cur_var = match.group()
                    pos = match.span()
                    if cur_var.startswith("${") and cur_var.endswith("}"):
                        cur_var = "$" + cur_var[2:-1]

                    if cur_var.startswith("$") and "." not in cur_var:
                        var = cur_var.replace("$", "")
                        if var not in bp_inputs:
                            self._add_diagnostic(
                                Position(line=input.value.start[0], character=input.value.start[1] + pos[0]),
                                Position(line=input.value.end[0], character=input.value.start[1] + pos[1]),
                                message=message.format(cur_var)
                            )
                    elif cur_var.lower().startswith("$colony"):
                        valid_var, error_message = self._is_valid_auto_var(cur_var)
                        if not valid_var:
                            self._add_diagnostic(
                                Position(line=input.value.start[0], character=input.value.start[1] + pos[0]),
                                Position(line=input.value.end[0], character=input.value.start[1] + pos[1]),
                                message=error_message
                            )

    def _validate_apps_and_services_are_unique(self):
        # check that there are no duplicate names in the apps being used
        duplicated = {}
        apps = {}
        for app in self._tree.apps_node.items:
            if app.id.text not in apps:
                apps[app.id.text] = app
            else:
                self._add_diagnostic(
                    Position(line=app.id.start[0], character=app.start[1]),
                    Position(line=app.id.end[0], character=app.id.end[1]),
                    message="This application is already defined. Each application should be defined only once."
                )
                if app.id.text not in duplicated:
                    prev_app = apps[app.id.text]
                    self._add_diagnostic(
                        Position(line=prev_app.id.start[0], character=prev_app.start[1]),
                        Position(line=prev_app.id.end[0], character=prev_app.id.end[1]),
                        message="This application is already defined. Each application should be defined only once."
                    )
                    duplicated[app.id.text] = 1
            
        # check that there are no duplicate names in the services being used
        srvs = {}
        for srv in self._tree.services_node.items:
            if srv.id.text not in srvs:
                srvs[srv.id.text] = srv
            else:
                self._add_diagnostic(
                    Position(line=srv.id.start[0], character=srv.start[1]),
                    Position(line=srv.id.end[0], character=srv.id.end[1]),
                    message="This service is already defined. Each service should be defined only once."
                )
                if srv.id.text not in duplicated:
                    prev_srv = srvs[srv.id.text]
                    self._add_diagnostic(
                        Position(line=prev_srv.id.start[0], character=prev_srv.start[1]),
                        Position(line=prev_srv.id.end[0], character=prev_srv.id.end[1]),
                        message="This service is already defined. Each service should be defined only once."
                    )
                    duplicated[srv.id.text] = 1
            
            # check that there is no app with this name
            if srv.id.text in apps:
                self._add_diagnostic(
                    Position(line=srv.id.start[0], character=srv.start[1]),
                    Position(line=srv.id.end[0], character=srv.id.end[1]),
                    message="There is already an application with the same name in this blueprint. Make sure the names are unique."
                )
                prev_app = apps[srv.id.text]
                self._add_diagnostic(
                    Position(line=prev_app.id.start[0], character=prev_app.start[1]),
                    Position(line=prev_app.id.end[0], character=prev_app.id.end[1]),
                    message="There is already a service with the same name in this blueprint. Make sure the names are unique."
                )
    
    def _validate_artifaces_apps_are_defined(self):
        for art in self._tree.artifacts:
            if art.key.text not in self.blueprint_apps:
                self._add_diagnostic(
                    Position(line=art.key.start[0], character=art.start[1]),
                    Position(line=art.key.end[0], character=art.key.end[1]),
                    message="This application is not defined in this blueprint."
                )
    
    def _validate_artifaces_are_unique(self):
        arts = {}
        duplicated = {}
        for art in self._tree.artifacts:
            if art.key.text not in arts:
                arts[art.key.text] = art
            else:
                self._add_diagnostic(
                    Position(line=art.key.start[0], character=art.start[1]),
                    Position(line=art.key.end[0], character=art.key.end[1]),
                    message="This artifact is already defined. Each artifact should be defined only once."
                )
                if art.key.text not in duplicated:
                    prev_art = arts[art.key.text]
                    self._add_diagnostic(
                        Position(line=prev_art.key.start[0], character=prev_art.start[1]),
                        Position(line=prev_art.key.end[0], character=prev_art.key.end[1]),
                        message="This artifact is already defined. Each artifact should be defined only once."
                    )
                    duplicated[prev_art.key.text] = 1
    
    def _validate_apps_inputs_exists(self):
        for app in self._tree.apps_node.items:
            app_inputs = applications.get_app_inputs(app.id.text)
            for input in app.inputs_node.inputs:
                if input.key.text not in app_inputs:
                    self._add_diagnostic(
                        Position(line=input.key.start[0], character=input.start[1]),
                        Position(line=input.key.end[0], character=input.key.end[1]),
                        message=f"The application '{app.id.text}' does not have an input named '{input.key.text}'"
                    )
            
    def _validate_services_inputs_exists(self):
        for srv in self._tree.services_node.items:
            srv_inputs = services.get_service_inputs(srv.id.text)
            for input in srv.inputs_node.inputs:
                if input.key.text not in srv_inputs:
                    self._add_diagnostic(
                        Position(line=input.key.start[0], character=input.start[1]),
                        Position(line=input.key.end[0], character=input.key.end[1]),
                        message=f"The service '{srv.id.text}' does not have an input named '{input.key.text}'"
                    )
     
    def validate(self):
        # prep
        _ = applications.get_available_applications(self._root_path)
        _ = services.get_available_services(self._root_path)
        # warnings
        self._check_for_unused_blueprint_inputs()
        # errors
        self._validate_dependency_exists()
        self._validate_var_being_used_is_defined()
        self._validate_non_existing_app_is_used()
        self._validate_non_existing_service_is_used()
        self._validate_apps_and_services_are_unique()
        self._validate_artifaces_apps_are_defined()
        self._validate_artifaces_are_unique()
        self._validate_apps_inputs_exists()
        self._validate_services_inputs_exists()
        return self._diagnostics
