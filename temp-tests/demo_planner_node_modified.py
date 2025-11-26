#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool
import threading
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

USE_Z_AS_FORWARD = True

# Define routes for 4 solar panels
SOLAR_PANEL_ROUTES = {
    1: [
        # Panel 1 route
        (0, -1.2),   # Start
        (0, 0.2),    # Approach panel
        (-0.5, 0.2), # Panel position (wait point)
        (0, 0.2),    # Back away
        (0, -1.2),   # Return to start
    ],
    2: [
        # Panel 2 route
        (0, -1.2),   # Start
        (0, 0.2),    # Approach panel
        (0.5, 0.2),  # Panel position (wait point)
        (0, 0.2),    # Back away
        (0, -1.2),   # Return to start
    ],
    3: [
        # Panel 3 route
        (0, -1.2),   # Start
        (-0.5, -1.1), # Panel position (wait point)
        (0, -1.2),   # Return to start
    ],
    4: [
        # Panel 4 route
        (0, -1.2),   # Start
        (0.5, -1.1), # Panel position (wait point)
        (0, -1.2),   # Return to start
    ],
}

class CommandHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving SLM commands"""
    planner_node = None  # Will be set by PlannerNode
    
    def do_POST(self):
        if self.path == '/start_route':
            try:
                length = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                
                route_number = data.get('route_number')
                task_id = data.get('task_id')
                webhook_url = data.get('webhook_url')
                
                # Validate required fields
                if route_number is None:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Missing route_number'}).encode('utf-8'))
                    return
                
                if task_id is None:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Missing task_id'}).encode('utf-8'))
                    return
                
                # Validate route_number is in valid range (1-4)
                if route_number not in SOLAR_PANEL_ROUTES:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'error': f'Invalid route_number: {route_number}. Must be 1-4'
                    }).encode('utf-8'))
                    return
                
                # Trigger route start (non-blocking, just sets variables)
                if self.planner_node:
                    self.planner_node.start_route(route_number, task_id, webhook_url)
                else:
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Planner node not initialized'}).encode('utf-8'))
                    return
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({
                    'status': 'ok',
                    'route': route_number,
                    'task_id': task_id
                })
                self.wfile.write(response.encode('utf-8'))
                
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Invalid JSON: {str(e)}'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress HTTP logs (optional)
        pass

class PlannerNode(Node):
    """
    Publishes one goal at a time on /planner/goal.
    Now accepts HTTP commands to start specific routes.
    """
    def __init__(self):
        super().__init__("demo_planner_node")

        # Latched-like QoS so new subscribers get the last goal
        goal_qos = QoSProfile(depth=1)
        goal_qos.reliability = ReliabilityPolicy.RELIABLE
        goal_qos.history = HistoryPolicy.KEEP_LAST
        goal_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.current_route = None  # No auto-start
        self.idx = 0
        self.waypoints = []
        self.goal_pub = self.create_publisher(PoseStamped, "/planner/goal", goal_qos)
        self.reached_sub = self.create_subscription(Bool, "/controller/goal_reached", self._reached_cb, 10)
        
        # Task tracking for webhook
        self.task_id = None
        self.webhook_url = None

        self._last_goal_msg = None
        # Republish current goal at 2 Hz until acked
        self._republish_timer = self.create_timer(0.5, self._republish_current_goal)
        
        # Flag to track if we're waiting at panel position
        self._waiting_at_panel = False
        self._wait_timer = None

        # Start HTTP server in background thread
        self._start_http_server()
        
        self.get_logger().info("✅ Planner Node ready. Waiting for commands on http://0.0.0.0:5001/start_route")

    def _start_http_server(self):
        """Start HTTP server in daemon thread (non-blocking)"""
        CommandHandler.planner_node = self
        
        def run_server():
            server = HTTPServer(('0.0.0.0', 5001), CommandHandler)
            self.get_logger().info("🌐 HTTP server started on port 5001")
            server.serve_forever()
        
        http_thread = threading.Thread(target=run_server, daemon=True)
        http_thread.start()

    def start_route(self, route_number, task_id, webhook_url):
        """Called by HTTP handler to start a specific route"""
        # Cancel any existing wait timer
        if self._wait_timer:
            self._wait_timer.cancel()
            self._wait_timer = None
        self._waiting_at_panel = False
        
        self.current_route = route_number
        self.idx = 0
        self.waypoints = SOLAR_PANEL_ROUTES[route_number]
        self.task_id = task_id
        self.webhook_url = webhook_url
        
        self.get_logger().info(f"🚀 Starting Panel Route {route_number} (task: {task_id})")
        self._publish_current_goal()

    def _publish_current_goal(self):
        if not self.waypoints:
            return
        
        x, fwd = self.waypoints[self.idx]
        axis = "z" if USE_Z_AS_FORWARD else "y"
        msg = PoseStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x = float(x)
        if USE_Z_AS_FORWARD:
            msg.pose.position.z = float(fwd)
        else:
            msg.pose.position.y = float(fwd)
        msg.pose.orientation.w = 1.0

        self._last_goal_msg = msg
        self.goal_pub.publish(msg)
        self.get_logger().info(f"Planner [Route {self.current_route}] -> goal #{self.idx+1}/{len(self.waypoints)}: (x={x:.3f}, {axis}={fwd:.3f}) [published]")

    def _republish_current_goal(self):
        if self._last_goal_msg is None:
            return
        # refresh timestamp to avoid ancient headers
        self._last_goal_msg.header.stamp = self.get_clock().now().to_msg()
        self.goal_pub.publish(self._last_goal_msg)

    def _send_webhook(self, status):
        """Send webhook to SLM backend"""
        if not self.webhook_url or not self.task_id:
            return
        
        try:
            # Format timestamp as ISO-8601
            now = self.get_clock().now()
            timestamp_iso = now.to_msg().sec + now.to_msg().nanosec / 1e9
            timestamp_str = datetime.fromtimestamp(timestamp_iso, tz=timezone.utc).isoformat()
            
            response = requests.post(
                self.webhook_url,
                json={
                    "task_id": self.task_id,
                    "status": status,
                    "panel_id": f"P-{self.current_route:03d}",
                    "timestamp": timestamp_str,
                    "position": {
                        "x": self.waypoints[self.idx][0] if self.idx < len(self.waypoints) else 0,
                        "z": self.waypoints[self.idx][1] if self.idx < len(self.waypoints) else 0
                    }
                },
                timeout=2
            )
            self.get_logger().info(f"📡 Webhook sent: {status} -> HTTP {response.status_code}")
        except Exception as e:
            self.get_logger().error(f"❌ Webhook failed: {e}")

    def _continue_after_wait(self):
        """Continue to next waypoint after 3-second wait at panel position."""
        if not self._waiting_at_panel:
            return
        
        self._waiting_at_panel = False
        if self._wait_timer:
            self._wait_timer.cancel()
            self._wait_timer = None
        
        # Send "cleaning_done" webhook
        self._send_webhook("cleaning_done")
        
        self.get_logger().info("✨ 3-second wait completed (cleaning done), continuing...")
        
        # Proceed to next waypoint
        self.idx += 1
        if self.idx < len(self.waypoints):
            self._publish_current_goal()
        else:
            self.get_logger().info(f"✅ Panel Route {self.current_route} completed!")
            
            # Send "returned" webhook
            self._send_webhook("returned")
            
            # Reset task tracking
            self.task_id = None
            self.webhook_url = None
            self.current_route = None

    def _reached_cb(self, msg: Bool):
        if not msg.data:
            return
        
        # Prevent processing if we're already waiting at a panel
        if self._waiting_at_panel:
            return
        
        self._last_goal_msg = None  # stop republishing current
        
        # Check if we just reached the panel position waypoint (wait point)
        wait_indices = {1: 2, 2: 2, 3: 1, 4: 1}
        wait_idx = wait_indices.get(self.current_route, -1)
        
        if self.idx == wait_idx:
            # Arrived at panel position!
            x, z = self.waypoints[self.idx]
            self.get_logger().info(f"🤖 Reached panel waypoint ({x:.1f}, {z:.1f}) on Route {self.current_route}")
            
            # Send "arrived" webhook
            self._send_webhook("arrived")
            
            self.get_logger().info("⏳ Waiting 3 seconds (simulating cleaning)...")
            self._waiting_at_panel = True
            
            # Cancel any existing timer
            if self._wait_timer:
                self._wait_timer.cancel()
            
            # Wait 3 seconds then continue
            self._wait_timer = self.create_timer(3.0, self._continue_after_wait)
        else:
            # Normal progression for other waypoints
            self.idx += 1
            if self.idx < len(self.waypoints):
                self._publish_current_goal()
            else:
                self.get_logger().info(f"✅ Panel Route {self.current_route} completed!")
                
                # Send "returned" webhook (if we haven't already at panel position)
                if self.current_route in [3, 4]:  # Routes 3&4 have shorter paths
                    self._send_webhook("returned")
                
                # Reset task tracking
                self.task_id = None
                self.webhook_url = None
                self.current_route = None

def main():
    rclpy.init()
    node = PlannerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()

