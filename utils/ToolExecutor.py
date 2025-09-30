import requests
import json
from urllib.parse import urljoin

class ToolExecutor:
    def __init__(self, go_server_base_url: str):
        """
        Initializes the ToolExecutor with the base URL of the Go backend server.
        """
        self.base_url = go_server_base_url

    def execute_tool(self, tool_name: str, parameters: dict):
        """
        Executes a tool call by dispatching to the appropriate handler function.
        """
        tool_handlers = {
            "find_panels": self.find_panels,
            "get_panel_maintenance_history": self.get_panel_maintenance_history,
            "dispatch_drone_to_cluster": self.dispatch_drone_to_cluster,
            "dispatch_rover_to_panel": self.dispatch_rover_to_panel,
            "get_drone_status": self.get_drone_status,
        }

        handler = tool_handlers.get(tool_name)
        if handler:
            return handler(parameters)
        else:
            return {"error": f"Tool '{tool_name}' not found."}


    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """
        A helper function to make HTTP requests to the Go backend.
        """
        url = urljoin(self.base_url, endpoint)
        try:
            response = requests.request(method, url, params=params, json=data, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            if response.status_code == 204: # No Content
                return {"status": "success", "message": "Request successful with no content returned."}
            return response.json()
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP error occurred: {e.response.status_code} {e.response.reason}", "details": e.response.text}
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to call Go backend endpoint '{endpoint}': {e}"}
    

    def find_panels(self, parameters: dict) -> dict:
        """
        Handles the 'find_panels' tool by calling GET /api/panels with optional filters.
        """
        # Rename keys to match the Go API query parameters if necessary
        query_params = {
            "clusterid": parameters.get("cluster_id"),
            "panelid": parameters.get("panel_id"),
            "status": parameters.get("status"),
        }
        # Filter out None values so they are not included in the query string
        cleaned_params = {k: v for k, v in query_params.items() if v is not None}
        return self._make_request("GET", "api/panels", params=cleaned_params)

    def get_panel_maintenance_history(self, parameters: dict) -> dict:
        """
        Handles 'get_panel_maintenance_history' by calling GET /api/maintenance_requests.
        """
        cluster_id = parameters.get("cluster_id")
        panel_id = parameters.get("panel_id")

        if not cluster_id or not panel_id:
            return {"error": "cluster_id and panel_id are required parameters."}

        query_params = {
            "clusterid": cluster_id,
            "panelid": panel_id,
        }
        return self._make_request("GET", "api/maintenance_requests", params=query_params)

    def dispatch_drone_to_cluster(self, parameters: dict) -> dict:
        """
        Handles 'dispatch_drone_to_cluster' by calling POST /api/drones/send/{cluster_id}.
        """
        cluster_id = parameters.get("cluster_id")
        if not cluster_id:
            return {"error": "cluster_id is a required parameter."}
        
        endpoint = f"api/drones/send/{cluster_id}"
        return self._make_request("POST", endpoint)



    def dispatch_rover_to_panel(self, parameters: dict) -> dict:
        """
        Handles 'dispatch_rover_to_panel'.
        NOTE: This is a placeholder as the exact API endpoint needs confirmation.
        Assuming it will be POST /api/rover/send/{cluster_id}/{panel_id}.
        """
        cluster_id = parameters.get("cluster_id")
        panel_id = parameters.get("panel_id")
        if not cluster_id or not panel_id:
            return {"error": "cluster_id and panel_id are required parameters."}

        # This endpoint is an assumption based on `handlers.go` and needs to be verified.
        # For now, it returns a mock success message.
        # endpoint = f"api/rover/send/{cluster_id}/{panel_id}"
        # return self._make_request("POST", endpoint)
        
        print(f"--- MOCK CALL ---: Dispatching rover to Cluster {cluster_id}, Panel {panel_id}")
        return {"status": "success", "message": f"Rover dispatched to cluster {cluster_id}, panel {panel_id}. (Mock Response)"}

    def get_drone_status(self, parameters: dict) -> dict:
        """
        Handles the 'get_drone_status' tool by calling GET /api/drones with optional filters.
        """
        query_params = {
            "droneid": parameters.get("drone_id"),
            "destination": parameters.get("destination_cluster_id"),
        }
        cleaned_params = {k: v for k, v in query_params.items() if v is not None}
        return self._make_request("GET", "api/drones", params=cleaned_params)