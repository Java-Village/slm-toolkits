import requests
import json


class ToolExecutor:
    def __init__(self, go_server_base_url: str):
        self.base_url = go_server_base_url

    def execute_tool(self, tool_name: str, parameters: dict):
        """
        Executes a tool call by making an HTTP request to the Go backend server.
        This acts as a dispatcher.
        """
        if tool_name == "list_all_agents":
            return self.list_all_agents(parameters)
        elif tool_name == "get_panel_status":
            return self.get_panel_status(parameters)

        else:
            return {"error": f"Tool {tool_name} not found."}

    def list_all_panels(self, parameters: dict) -> dict:
        """
        Handles the 'list_all_panels' tool by calling the Go server's GET /api/panels endpoint.
        """
        try:
            # The 'parameters' might be empty for this tool, which is fine.
            # We can add support for passing query params later if needed.
            response = requests.get(f"{self.base_url}/api/panels")
            response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to call Go backend for list_all_panels: {e}"}

    def get_panel_status(self, parameters: dict) -> dict:
        """
        Handles the 'get_panel_status' tool by calling the Go server's GET /api/panels endpoint
        with query parameters.
        """
        panel_id = parameters.get("panel_id")
        if not panel_id:
            return {"error": "panel_id is a required parameter for get_panel_status."}

        try:
            # Assuming panel_id format is "P-001" and we need to extract cluster and panel numbers.
            # This logic will need to be confirmed with the Go backend developer.
            # For now, let's assume a simple query.
            # We'll need to clarify how to map "P-001" to clusterid and panelid.
            # Let's placeholder this logic for now.
            
            # Placeholder: Let's assume we can query by a string ID for now.
            # We will need to adjust this based on the actual API capabilities.
            # For this example, I'll pretend the API supports a `panel_full_id` query param.
            # In reality, we'll need to parse 'P-001' into cluster and panel numbers.
            
            # This is a placeholder call and will likely need to be changed
            # response = requests.get(f"{self.base_url}/api/panels?panel_full_id={panel_id}")
            
            # Let's just return a mock success message for now until we clarify the API
            return {"status": f"Successfully retrieved status for panel {panel_id}. (Implementation Pending)"}

        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to call Go backend for get_panel_status: {e}"}