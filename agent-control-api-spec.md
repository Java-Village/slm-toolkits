# Agent Control API Specification

This document defines the API interface that the `CoordinateServer` will use to communicate with the underlying Agents (Drones and Rovers). This API interface will be responsible for receiving commands, querying status, and acting as a bridge between the `CoordinateServer` and the actual hardware or its simulation.

---

## 1. API Basic Information

*   **Base URL**: `/api/v1` (e.g., if the Agent Control API runs on `http://localhost:8001`, the full path would be `http://localhost:8001/api/v1`)
*   **Authentication**: To be determined (simplified for initial phase, consider API Key or OAuth later)
*   **Content Type**: `application/json`

---

## 2. Endpoint Definitions

### 2.1. Get All Agents List

`GET /agents`

*   **Description**: Retrieves a list of all registered Drone and Rover Agents, including their basic information and current status.
*   **Request**:
    *   **Header**: None
    *   **Body**: None
*   **Response**:
    *   **Status Code**: `200 OK`
    *   **Body**: `application/json`
        ```json
        [
          {
            "agent_id": "D-001",
            "type": "drone",
            "status": "idle",
            "battery_level": 95.5,
            "current_position": {"latitude": 34.0522, "longitude": -118.2437},
            "capabilities": ["inspection", "cleaning"]
          },
          {
            "agent_id": "R-001",
            "type": "rover",
            "status": "busy",
            "battery_level": 80.0,
            "current_position": {"latitude": 34.0500, "longitude": -118.2500},
            "capabilities": ["collect_sample", "perform_maintenance"],
            "current_task_id": "TASK-ROVER-001"
          }
        ]
        ```
    *   **Error Response**:
        *   `500 Internal Server Error`: Internal server error.

---

### 2.2. Get Specific Agent Status

`GET /agents/{agent_id}/status`

*   **Description**: Retrieves the detailed real-time status of a specific Agent.
*   **Path Parameters**:
    *   `agent_id` (string, required): The unique identifier of the Agent (e.g., `D-001`, `R-001`).
*   **Request**:
    *   **Header**: None
    *   **Body**: None
*   **Response**:
    *   **Status Code**: `200 OK`
    *   **Body**: `application/json`
        ```json
        {
          "agent_id": "D-001",
          "type": "drone",
          "status": "idle",
          "battery_level": 95.5,
          "current_position": {"latitude": 34.0522, "longitude": -118.2437},
          "capabilities": ["inspection", "cleaning"],
          "last_updated": "2025-09-26T10:30:00Z"
        }
        ```
    *   **Error Response**:
        *   `404 Not Found`: The specified `agent_id` does not exist.
        *   `500 Internal Server Error`: Internal server error.

---

### 2.3. Dispatch Agent for a Task

`POST /agents/{agent_id}/dispatch`

*   **Description**: Sends a dispatch command to a specific Agent to perform a task.
*   **Path Parameters**:
    *   `agent_id` (string, required): The unique identifier of the Agent.
*   **Request**:
    *   **Header**: `Content-Type: application/json`
    *   **Body**: `application/json`
        ```json
        {
          "task_type": "inspection",
          "parameters": {
            "destination": {"latitude": 34.0600, "longitude": -118.2000},
            "target_panel_id": "P-005"
          }
        }
        ```
        *   `task_type` (string, required): The type of task (e.g., `inspection`, `cleaning`, `collect_sample`).
        *   `parameters` (object, required): All parameters required for the task. Specific content depends on `task_type`.
            *   `destination` (object, optional): Target latitude and longitude.
            *   `target_panel_id` (string, optional): The ID of the solar panel related to the task.
*   **Response**:
    *   **Status Code**: `202 Accepted`
    *   **Body**: `application/json`
        ```json
        {
          "message": "Task dispatched successfully.",
          "task_id": "TASK-D-001-20250926-001",
          "agent_id": "D-001",
          "status_url": "/api/v1/tasks/TASK-D-001-20250926-001/status"
        }
        ```
        *   `message` (string): Result message of the operation.
        *   `task_id` (string): A unique identifier generated for this task. The `CoordinateServer` will use this ID to track task progress.
        *   `agent_id` (string): The ID of the dispatched Agent.
        *   `status_url` (string): The API path that can be used to query the status of this task.
    *   **Error Response**:
        *   `400 Bad Request`: Invalid request parameters.
        *   `404 Not Found`: The specified `agent_id` does not exist.
        *   `409 Conflict`: Agent is unavailable (e.g., already performing another task).
        *   `500 Internal Server Error`: Internal server error.