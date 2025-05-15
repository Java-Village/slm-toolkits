🔍 Sample DroneStatus JSON
# Status : dirty, clean, unknown, broken
```JSON
[
  {
    "cluster_id": "CL-001",
    "location": { "x": 3, "y": 3 },
    "panels": [
      {
        "panel_id": "P-001",
        "status": "clean",
        "latest_status_time": "2025-05-15T09:00:00Z",
        "most_recent_repair": "2025-04-30T13:45:00Z",
        "offset": { "x": -2, "y": 2 },
        "history": [
          { "type": "repair", "date": "2025-04-30", "action": "replaced connector" },
          { "type": "inspection", "date": "2025-05-10", "result": "normal" }
        ]
      },
      {
        "panel_id": "P-002",
        "status": "dirty",
        "latest_status_time": "2025-05-14T15:30:00Z",
        "most_recent_repair": "2025-04-10T10:00:00Z",
        "offset": { "x": 2, "y": 2 },
        "history": [
          { "type": "inspection", "date": "2025-05-14", "result": "dust buildup" }
        ]
      },
      {
        "panel_id": "P-003",
        "status": "unknown",
        "latest_status_time": "2025-05-13T17:20:00Z",
        "most_recent_repair": "2025-03-25T08:00:00Z",
        "offset": { "x": -2, "y": -2 },
        "history": [
          { "type": "repair", "date": "2025-03-25", "action": "replaced inverter" },
          { "type": "inspection", "date": "2025-05-13", "result": "power loss" }
        ]
      },
      {
        "panel_id": "P-004",
        "status": "dirty",
        "latest_status_time": "2025-05-15T07:00:00Z",
        "most_recent_repair": "2025-01-10T12:00:00Z",
        "offset": { "x": 2, "y": -2 },
        "history": [
          { "type": "inspection", "date": "2025-05-14", "result": "normal" }
        ]
      }
    ]
  }
]


```
