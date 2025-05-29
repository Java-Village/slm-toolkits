# Coordinate Server System Specification

## System Components Interaction (Conceptual Diagram)

```mermaid
sequenceDiagram
    participant Frontend
    participant CoordinateServer
    participant LLM
    participant Database

    Frontend->>CoordinateServer: POST /api/command
    CoordinateServer->>LLM: Forward command
    LLM->>Database: Query data
    Database-->>LLM: Return data
    LLM-->>CoordinateServer: Structured response
    CoordinateServer-->>Frontend: Processed result
```

## 1. LLM Command Types

### 1.1 Database Queries

#### Input Format

```json
{
  "tool": {
    "name": "db",
    "parameters": {
      "target": "panel|rover|drone",
      "query": "status|battery|position|history|current_operation|maintenance|condition",
      "id": "id|keywords|position"
    }
  }
}
```

#### Parameter Details

- `target`: Specifies the type of entity to query

  - `panel`: Solar panel information
  - `rover`: Ground maintenance vehicle information
  - `drone`: Aerial vehicle information

- `query`: Type of information to retrieve

  - `status`: Current operational status
  - `battery`: Battery level and charging status
  - `position`: Current coordinates
  - `history`: Maintenance and operation history
  - `current_operation`: Active task information
  - `maintenance`: Maintenance schedule and history
  - `condition`: Physical condition assessment

- `id`: Identifier for the target
  - Can be specific ID (e.g., "SP-001")
  - Keywords (e.g., "west", "north")
  - Position coordinates

#### Output Format

```json
{
  "status": "success",
  "data": {
    // Panel specific response
    "panel_status": "operational|maintenance|error",
    "last_maintenance": "2024-03-20T10:30:00Z",
    "condition": "good|fair|poor",
    "position": {
      "x": 123.45,
      "y": 67.89,
      "z": 10.0
    },
    "battery_level": 85,
    "efficiency": 95.5,
    "maintenance_history": [
      {
        "date": "2024-03-20T10:30:00Z",
        "type": "cleaning",
        "status": "completed"
      }
    ]
  },
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Response Fields

- `panel_status`: Current operational state
- `last_maintenance`: Timestamp of last maintenance
- `condition`: Physical condition assessment
- `position`: 3D coordinates
- `battery_level`: Current battery percentage
- `efficiency`: Current energy conversion efficiency
- `maintenance_history`: Array of maintenance records

#### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "DB_QUERY_ERROR",
    "message": "Failed to retrieve panel information",
    "details": {
      "reason": "Panel not found",
      "suggested_action": "Verify panel ID"
    }
  },
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Common Error Codes

- `DB_QUERY_ERROR`: General database query failure
- `INVALID_TARGET`: Unsupported target type
- `INVALID_QUERY`: Unsupported query type
- `NOT_FOUND`: Target entity not found
- `DB_CONNECTION_ERROR`: Database connection failure

### 1.2 Task Assignment

#### Input Format

```json
{
    "tool": {
        "name": "assign",
        "parameters": {
            "drone_id": "string",
            "task": "string",
            "panel_id": "string",
            "position": {
                "x": number,
                "y": number,
                "z": number
            }
        }
    }
}
```

#### Parameter Details

- `drone_id`: Identifier of the drone to assign

  - Format: "D-XXX" where XXX is a unique number
  - Example: "D-001", "D-002"

- `task`: Type of task to assign

  - `clean`: Panel cleaning operation
  - `inspect`: Visual inspection
  - `maintenance`: General maintenance
  - `emergency`: Emergency response

- `panel_id`: Target panel identifier

  - Format: "SP-XXX" where XXX is a unique number
  - Example: "SP-001", "SP-002"

- `position`: 3D coordinates of the target
  - `x`: East-West position (meters)
  - `y`: North-South position (meters)
  - `z`: Altitude (meters)

#### Output Format

```json
{
  "status": "success",
  "task_id": "T-20240321-001",
  "assigned_to": "D-001",
  "task_type": "clean",
  "target": "SP-001",
  "estimated_completion": "2024-03-21T09:30:00Z",
  "priority": "normal|high|urgent",
  "status": "assigned|in_progress|completed|failed",
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Response Fields

- `task_id`: Unique task identifier
- `assigned_to`: Drone identifier
- `task_type`: Type of assigned task
- `target`: Target panel identifier
- `estimated_completion`: Expected completion time
- `priority`: Task priority level
- `status`: Current task status

#### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "ASSIGNMENT_ERROR",
    "message": "Failed to assign task",
    "details": {
      "reason": "Drone not available",
      "suggested_action": "Try different drone or wait"
    }
  },
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Common Error Codes

- `ASSIGNMENT_ERROR`: General assignment failure
- `DRONE_UNAVAILABLE`: Drone is busy or offline
- `INVALID_TASK`: Unsupported task type
- `INVALID_POSITION`: Invalid coordinates
- `PANEL_NOT_FOUND`: Target panel not found

### 1.3 Task List Query

#### Input Format

```json
{
  "tool": {
    "name": "tasklist",
    "parameters": {
      "filter": {
        "status": "pending|in_progress|completed",
        "type": "clean|inspect|maintenance",
        "priority": "normal|high|urgent"
      },
      "time_range": {
        "start": "2024-03-21T00:00:00Z",
        "end": "2024-03-21T23:59:59Z"
      }
    }
  }
}
```

#### Parameter Details

- `filter`: Optional filtering criteria

  - `status`: Task status filter
  - `type`: Task type filter
  - `priority`: Priority level filter

- `time_range`: Optional time period
  - `start`: Start timestamp
  - `end`: End timestamp

#### Output Format

```json
{
  "status": "success",
  "data": {
    "tasks": [
      {
        "task_id": "T-20240321-001",
        "type": "clean",
        "assigned_to": "D-001",
        "target": "SP-001",
        "status": "in_progress",
        "priority": "normal",
        "start_time": "2024-03-21T08:00:00Z",
        "estimated_completion": "2024-03-21T09:30:00Z",
        "progress": 45
      }
    ],
    "summary": {
      "total": 10,
      "pending": 3,
      "in_progress": 5,
      "completed": 2,
      "failed": 0
    }
  },
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Response Fields

- `tasks`: Array of task details

  - `task_id`: Unique task identifier
  - `type`: Task type
  - `assigned_to`: Assigned drone
  - `target`: Target panel
  - `status`: Current status
  - `priority`: Priority level
  - `start_time`: Task start time
  - `estimated_completion`: Expected completion
  - `progress`: Completion percentage

- `summary`: Task statistics
  - `total`: Total number of tasks
  - `pending`: Pending tasks
  - `in_progress`: Active tasks
  - `completed`: Completed tasks
  - `failed`: Failed tasks

#### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "TASKLIST_ERROR",
    "message": "Failed to retrieve task list",
    "details": {
      "reason": "Invalid time range",
      "suggested_action": "Check time range parameters"
    }
  },
  "timestamp": "2024-03-21T08:00:00Z"
}
```

#### Common Error Codes

- `TASKLIST_ERROR`: General task list retrieval failure
- `INVALID_FILTER`: Invalid filter parameters
- `INVALID_TIME_RANGE`: Invalid time period
- `DB_CONNECTION_ERROR`: Database connection failure

## 2. LLM Response Processing

### 2.1 Database Query Response

#### Response Format

```json
{
    "status": "success",
    "data": {
        "panel_status": "string",
        "last_maintenance": "timestamp",
        "condition": "string",
        "position": {
            "x": number,
            "y": number,
            "z": number
        }
    }
}
```

#### Response Processing Rules

1. Data Validation

   - Verify all required fields are present
   - Validate data types and formats
   - Check timestamp validity
   - Ensure position coordinates are within valid range

2. Status Mapping

   - Map internal status codes to user-friendly messages
   - Handle special cases and edge conditions
   - Maintain status history

3. Error Handling
   - Log all database errors
   - Provide meaningful error messages
   - Include recovery suggestions

### 2.2 Task Assignment Response

#### Response Format

```json
{
  "status": "success",
  "task_id": "string",
  "assigned_to": "string",
  "estimated_completion": "timestamp"
}
```

#### Response Processing Rules

1. Task ID Generation

   - Format: "T-YYYYMMDD-XXX"
   - Ensure uniqueness
   - Include timestamp for tracking

2. Assignment Validation

   - Verify drone availability
   - Check task compatibility
   - Validate resource allocation

3. Completion Estimation
   - Consider task type
   - Account for current workload
   - Include buffer time

### 2.3 Error Response

#### Response Format

```json
{
  "status": "error",
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

#### Error Processing Rules

1. Error Classification

   - System errors
   - Validation errors
   - Resource errors
   - Communication errors

2. Error Logging

   - Log error details
   - Include stack trace
   - Record timestamp
   - Track error frequency

3. Error Recovery
   - Define recovery procedures
   - Set retry limits
   - Implement fallback options

## 3. Frontend API Specification

### 3.1 Command Endpoint

#### Request Processing

1. Input Validation

   - Validate JSON format
   - Check required fields
   - Verify data types
   - Sanitize input

2. Authentication

   - Verify API key
   - Check user permissions
   - Validate session

3. Rate Limiting
   - Track request frequency
   - Implement throttling
   - Handle burst traffic

#### Response Processing

1. Data Formatting

   - Format timestamps
   - Convert units
   - Localize messages

2. Caching

   - Cache frequent queries
   - Set cache duration
   - Handle cache invalidation

3. Compression
   - Compress large responses
   - Set compression level
   - Handle different formats

## 4. Data Flow Specification

### 4.1 LLM to Database Flow

#### Data Flow Rules

1. Query Optimization

   - Use appropriate indexes
   - Optimize query patterns
   - Cache frequent queries

2. Data Consistency

   - Maintain ACID properties
   - Handle concurrent access
   - Implement rollback

3. Performance Monitoring
   - Track query performance
   - Monitor resource usage
   - Set performance alerts

### 4.2 Coordinate Server Processing

#### Processing Rules

1. Command Validation

   - Validate command format
   - Check parameter ranges
   - Verify dependencies

2. Resource Management

   - Track resource usage
   - Implement timeouts
   - Handle resource exhaustion

3. State Management
   - Maintain system state
   - Handle state transitions
   - Implement recovery

## 5. Response Types

### 5.1 Success Response

#### Response Rules

1. Data Formatting

   - Format numbers
   - Format dates
   - Format coordinates

2. Response Optimization

   - Minimize payload size
   - Use appropriate compression
   - Implement pagination

3. Caching Strategy
   - Set cache headers
   - Define cache duration
   - Handle cache updates

### 5.2 Error Response

#### Error Handling Rules

1. Error Classification

   - Client errors
   - Server errors
   - Network errors

2. Error Reporting

   - Log error details
   - Track error patterns
   - Generate reports

3. Recovery Procedures
   - Define retry logic
   - Set timeout values
   - Implement fallbacks

## 6. Command Processing Rules

### 6.1 Database Queries

#### Query Rules

1. Query Validation

   - Validate query syntax
   - Check parameter types
   - Verify permissions

2. Query Optimization

   - Use appropriate indexes
   - Optimize joins
   - Limit result size

3. Error Handling
   - Handle timeouts
   - Manage connections
   - Implement retries

### 6.2 Task Assignment

#### Assignment Rules

1. Resource Validation

   - Check availability
   - Verify capabilities
   - Validate permissions

2. Task Scheduling

   - Set priorities
   - Handle conflicts
   - Manage dependencies

3. Monitoring
   - Track progress
   - Handle timeouts
   - Manage failures

### 6.3 Task List

#### List Management Rules

1. Filtering

   - Apply filters
   - Sort results
   - Paginate data

2. Status Tracking

   - Update status
   - Track progress
   - Handle changes

3. Performance
   - Optimize queries
   - Cache results
   - Handle updates

## 7. Error Handling

### 7.1 Database Errors

#### Error Types

1. Connection Errors

   - Timeout
   - Connection lost
   - Authentication failed

2. Query Errors

   - Syntax error
   - Parameter error
   - Permission denied

3. Data Errors
   - Constraint violation
   - Data type mismatch
   - Missing data

### 7.2 Task Assignment Errors

#### Error Categories

1. Resource Errors

   - Unavailable
   - Incompatible
   - Overloaded

2. Validation Errors

   - Invalid parameters
   - Missing data
   - Format error

3. System Errors
   - Timeout
   - Communication error
   - Internal error

### 7.3 General Errors

#### Error Management

1. Error Logging

   - Log details
   - Track patterns
   - Generate alerts

2. Error Recovery

   - Retry logic
   - Fallback options
   - Manual intervention

3. Error Prevention
   - Input validation
   - Resource monitoring
   - System checks
