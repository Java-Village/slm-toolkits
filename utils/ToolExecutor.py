import requests
import json
import os
from urllib.parse import urljoin

# TODO: define webhook API
# currently, GO Backend sends webhook when:
#   - a task is assigned (to drone or rover)
#   - sending the drone/rover doesn't work
#   - status updates from the rover
#     - arrived at nav node, finished cleaning, returned to base, etc.
#     - but only when the status changes
#       - so it doesn't send the position of the rover every 5 seconds to the SLM

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
            "get_dashboard_status": self.get_dashboard_status,
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
        Handles the 'find_panels' tool by fetching live data from CoordinateServer.
        Falls back to mock data if server is unavailable.
        """
        print(f"[FIND_PANELS] Querying with params: {parameters}")
        
        # TODO: change to use `GET /api/panels` w/ various query params
        try:
            slm_url = os.getenv("SLM_URL", "http://localhost:8000")
            response = requests.get(f"{slm_url}/api/panels/status", timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                panels = data.get("panels", [])
                cluster_id = data.get("cluster_id", "CL-001")
                
                print(f"[FIND_PANELS] ✓ Retrieved {len(panels)} panels from live data")
                
                # Apply filters
                panel_id = parameters.get("panel_id")
                status_filter = parameters.get("status")
                cluster_filter = parameters.get("cluster_id")
                
                if status_filter:
                    panels = [p for p in panels if p["status"] == status_filter]
                
                if panel_id:
                    panels = [p for p in panels if p["panel_id"] == panel_id]
                
                if cluster_filter and cluster_filter != cluster_id:
                    panels = []
                
                # Format in the expected structure
                result = [{
                    "cluster_id": cluster_id,
                    "location": {"x": 3, "y": 3},
                    "panels": panels
                }]
                
                return {"panels": result}
                
        except Exception as e:
            print(f"[FIND_PANELS] ⚠ Could not fetch live data: {e}")
            print(f"[FIND_PANELS] Falling back to mock data")
        
        # FALLBACK: Mock data if server unavailable
        mock_data = [
            {
                "cluster_id": "CL-001",
                "location": {"x": 3, "y": 3},
                "panels": [
                    {
                        "panel_id": "P-001",
                        "status": "clean",
                        "latest_status_time": "2025-05-15T09:00:00Z",
                        "most_recent_repair": "2025-04-30T13:45:00Z",
                        "offset": {"x": -2, "y": 2},
                        "history": [
                            {"type": "repair", "date": "2025-04-30", "action": "replaced connector"},
                            {"type": "inspection", "date": "2025-05-10", "result": "normal"}
                        ]
                    },
                    {
                        "panel_id": "P-002",
                        "status": "dirty",
                        "latest_status_time": "2025-05-14T15:30:00Z",
                        "most_recent_repair": "2025-04-10T10:00:00Z",
                        "offset": {"x": 2, "y": 2},
                        "history": [
                            {"type": "inspection", "date": "2025-05-14", "result": "dust buildup"}
                        ]
                    },
                    {
                        "panel_id": "P-003",
                        "status": "unknown",
                        "latest_status_time": "2025-05-13T17:20:00Z",
                        "most_recent_repair": "2025-03-25T08:00:00Z",
                        "offset": {"x": -2, "y": -2},
                        "history": [
                            {"type": "repair", "date": "2025-03-25", "action": "replaced inverter"},
                            {"type": "inspection", "date": "2025-05-13", "result": "power loss"}
                        ]
                    },
                    {
                        "panel_id": "P-004",
                        "status": "dirty",
                        "latest_status_time": "2025-05-15T07:00:00Z",
                        "most_recent_repair": "2025-01-10T12:00:00Z",
                        "offset": {"x": 2, "y": -2},
                        "history": [
                            {"type": "inspection", "date": "2025-05-14", "result": "normal"}
                        ]
                    }
                ]
            }
        ]
        
        # Apply filtering on mock data
        cluster_id = parameters.get("cluster_id")
        panel_id = parameters.get("panel_id")
        status = parameters.get("status")
        
        if status:
            for cluster in mock_data:
                cluster["panels"] = [p for p in cluster["panels"] if p["status"] == status]
        
        if panel_id:
            for cluster in mock_data:
                cluster["panels"] = [p for p in cluster["panels"] if p["panel_id"] == panel_id]
        
        return {"panels": mock_data}

    def get_tasks_for_panel(self, parameters: dict) -> dict:
        """
        Handles 'get_tasks_for_panel' by calling GET /api/tasks.
        """
        # TODO: change to use `GET /api/tasks` with `cluster_id` and `panel_id` parameters
        
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
        # TODO: change to use `POST /api/tasks` w/ tasktype parameter "inspect"
        cluster_id = parameters.get("cluster_id")
        if not cluster_id:
            return {"error": "cluster_id is a required parameter."}
        
        endpoint = f"api/drones/send/{cluster_id}"
        return self._make_request("POST", endpoint)

    def dispatch_rover_to_panel(self, parameters: dict) -> dict:
        """
        Handles 'dispatch_rover_to_panel'.
        Generates task_id and prepares command for Rover.
        Supports flexible parameter formats (integers or strings).
        """

        # TODO: change to use `POST /api/tasks` w/ tasktype parameter "clean"
        import uuid
        
        cluster_id = parameters.get("cluster_id")
        panel_id = parameters.get("panel_id")
        if not cluster_id or not panel_id:
            return {"error": "cluster_id and panel_id are required parameters."}

        # Normalize cluster_id format (handle int or string input)
        if isinstance(cluster_id, int):
            cluster_id = f"CL-{cluster_id:03d}"  # Convert 1 -> "CL-001"
        elif not str(cluster_id).startswith("CL-"):
            cluster_id = f"CL-{cluster_id}"
        
        # Normalize panel_id format (handle int or string input)
        if isinstance(panel_id, int):
            panel_id = f"P-{panel_id:03d}"  # Convert 1 -> "P-001"
        elif not str(panel_id).startswith("P-"):
            panel_id = f"P-{panel_id}"
        
        # Map panel_id to route number (for Albert's rover planner)
        panel_to_route = {
            "P-001": 1,
            "P-002": 2,
            "P-003": 3,
            "P-004": 4
        }
        
        route_number = panel_to_route.get(panel_id)
        if not route_number:
            error_msg = f"Invalid panel_id: {panel_id}. Must be P-001 to P-004 (or 1 to 4)"
            print(f"[ERROR] {error_msg}")
            return {"error": error_msg}
        
        # Generate task_id
        task_id = str(uuid.uuid4())
        
        print(f"[ROVER DISPATCH] Task {task_id} -> Cluster {cluster_id}, Panel {panel_id} (Route {route_number})")
        
        # Send command to Rover via HTTP
        rover_url = os.getenv("ROVER_HTTP_URL", "http://localhost:5001/start_route")
        slm_url = os.getenv("SLM_URL", "http://localhost:8000")
        
        rover_command = {
            "route_number": route_number,
            "task_id": task_id,
            "webhook_url": f"{slm_url}/api/webhook/rover"
        }
        
        dispatch_success = False
        error_message = None
        
        try:
            response = requests.post(rover_url, json=rover_command, timeout=3)
            if response.status_code == 200:
                print(f"[ROVER DISPATCH] ✓ Command sent to Rover successfully")
                result = response.json()
                print(f"[ROVER DISPATCH] Rover response: {result}")
                dispatch_success = True
            else:
                error_message = f"Rover responded with status {response.status_code}"
                print(f"[ROVER DISPATCH] ⚠ {error_message}")
        except requests.exceptions.ConnectionError:
            error_message = f"Could not connect to Rover at {rover_url}. Make sure ROS planner node is running."
            print(f"[ROVER DISPATCH] ⚠ {error_message}")
        except requests.exceptions.Timeout:
            error_message = f"Request to Rover timed out after 3 seconds"
            print(f"[ROVER DISPATCH] ⚠ {error_message}")
        except Exception as e:
            error_message = f"Error communicating with Rover: {e}"
            print(f"[ROVER DISPATCH] ⚠ {error_message}")
        
        # Always return task_id and details, but indicate success/failure
        result = {
            "status": "dispatched" if dispatch_success else "failed",
            "task_id": task_id,
            "panel_id": panel_id,
            "cluster_id": cluster_id,
            "route_number": route_number,
        }
        
        if dispatch_success:
            result["message"] = f"Rover dispatched to panel {panel_id}. Task ID: {task_id}"
        else:
            result["error"] = error_message
            result["message"] = f"Failed to dispatch rover to panel {panel_id}. {error_message}"
            # Still return task_id so system can track the failed attempt
        
        return result

    def get_drone_status(self, parameters: dict) -> dict:
        """
        Handles the 'get_drone_status' tool by calling GET /api/drones with optional filters.
        """
        # TODO: change to use `GET /api/drones` with drone_id and some parameter to get most recent
        # text me (aydin) about this! haven't implemented the "get most recent" parameter yet
        query_params = {
            "droneid": parameters.get("drone_id"),
            "destination": parameters.get("destination_cluster_id"),
        }
        cleaned_params = {k: v for k, v in query_params.items() if v is not None}
        return self._make_request("GET", "api/drones", params=cleaned_params)


    def get_dashboard_status(self, parameters: dict) -> dict:
        """
        Handles 'get_dashboard_status' by fetching from CoordinateServer.
        Returns current system dashboard status including power output, efficiency, etc.
        """
        # TODO: i (aydin) gotta make a fake solar farm tracking API so text me when you get to this
        print(f"[GET_DASHBOARD] Fetching dashboard status")
        
        try:
            slm_url = os.getenv("SLM_URL", "http://localhost:8000")
            response = requests.get(f"{slm_url}/api/dashboard/status", timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[GET_DASHBOARD] ✓ Retrieved dashboard status: {json.dumps(data, indent=2)}")
                
                # Ensure we return a proper dict structure
                # Format the response for LLM understanding
                result = {
                    "status": "success",
                    "dashboard": {
                        "total_power_output_kw": data.get("total_power_output", 0),
                        "system_efficiency_percent": data.get("system_efficiency", 0),
                        "active_panels": data.get("active_panels", "0/0"),
                        "daily_revenue_usd": data.get("daily_revenue", 0),
                        "dirty_panel_count": data.get("dirty_panel_count", 0),
                        "has_active_rover_task": data.get("has_active_rover_task", False),
                        "normal_power_output_kw": data.get("normal_power_output", 0),
                        "normal_efficiency_percent": data.get("normal_efficiency", 0),
                        "normal_revenue_usd": data.get("normal_revenue", 0)
                    }
                }
                
                # Add summary message for LLM
                dirty_count = data.get("dirty_panel_count", 0)
                power_output = data.get("total_power_output", 0)
                efficiency = data.get("system_efficiency", 0)
                
                if dirty_count > 0:
                    result["summary"] = f"System has {dirty_count} dirty panel(s). Power output is {power_output} kW ({efficiency}% efficiency), which is below normal levels."
                else:
                    result["summary"] = f"All panels are clean. Power output is {power_output} kW ({efficiency}% efficiency), operating at normal levels."
                
                return result
            else:
                error_msg = f"Server error: {response.status_code}"
                print(f"[GET_DASHBOARD] ⚠ {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "message": "Unable to retrieve dashboard status"
                }
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Could not connect to SLM server: {e}"
            print(f"[GET_DASHBOARD] ⚠ {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "message": "Unable to connect to dashboard service"
            }
        except Exception as e:
            error_msg = f"Failed to fetch dashboard status: {e}"
            print(f"[GET_DASHBOARD] ⚠ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": error_msg,
                "message": "An error occurred while retrieving dashboard status"
            }
