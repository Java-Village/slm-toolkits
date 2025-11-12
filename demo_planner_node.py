#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool
import threading

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

class PlannerNode(Node):
    """
    Publishes one goal at a time on /planner/goal.
    - QoS: Transient Local (latched) so late subscribers get the last goal.
    - Also republishes at 2 Hz until the controller acks /controller/goal_reached.
    """
    def __init__(self):
        super().__init__("demo_planner_node")

        # Latched-like QoS so new subscribers get the last goal
        goal_qos = QoSProfile(depth=1)
        goal_qos.reliability = ReliabilityPolicy.RELIABLE
        goal_qos.history = HistoryPolicy.KEEP_LAST
        goal_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.current_route = 1  # Start with route 1
        self.idx = 0
        self.waypoints = SOLAR_PANEL_ROUTES[self.current_route]
        self.goal_pub = self.create_publisher(PoseStamped, "/planner/goal", goal_qos)
        self.reached_sub = self.create_subscription(Bool, "/controller/goal_reached", self._reached_cb, 10)
        
        self.get_logger().info(f"Starting Panel Route {self.current_route} with {len(self.waypoints)} waypoints")

        self._last_goal_msg = None
        # Republish current goal at 2 Hz until acked
        self._republish_timer = self.create_timer(0.5, self._republish_current_goal)
        
        # Flag to track if we're waiting at panel position
        self._waiting_at_panel = False
        self._wait_timer = None
        # self._waiting_for_input = False  # Commented out - no longer using Enter key
        # self._input_thread = None  # Commented out - no longer using Enter key

        # Publish first goal immediately
        self._publish_current_goal()

    def _start_next_route(self):
        """Start the next route in sequence."""
        # Cancel any existing wait timer when starting a new route
        if self._wait_timer:
            self._wait_timer.cancel()
            self._wait_timer = None
        self._waiting_at_panel = False
        
        self.current_route += 1
        if self.current_route > 4:
            self.get_logger().info("✅ All 4 panel routes completed!")
            self._last_goal_msg = None
            return False
        
        self.idx = 0
        self.waypoints = SOLAR_PANEL_ROUTES[self.current_route]
        self.get_logger().info(f"🔄 Starting Panel Route {self.current_route} with {len(self.waypoints)} waypoints")
        self._publish_current_goal()
        return True

    def _publish_current_goal(self):
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
        # Throttled info so you can see it's alive
        self.get_logger().debug("Re-publishing current goal (latched)")

    # def _wait_for_enter(self):
    #     """Wait for user to press Enter in a separate thread."""
    #     input()  # This blocks until Enter is pressed
    #     self._waiting_for_input = False
    #     self.get_logger().info("User pressed Enter, continuing to next waypoint...")
    #     # Now proceed to next waypoint
    #     self.idx += 1
    #     if self.idx < len(self.waypoints):
    #         self._publish_current_goal()
    #     else:
    #         self.get_logger().info(f"✅ Panel Route {self.current_route} completed!")
    #         # Move to next route
    #         if not self._start_next_route():
    #             # All routes completed
    #             pass

    def _continue_after_wait(self):
        """Continue to next waypoint after 3-second wait at panel position."""
        # Safety check: only proceed if we're actually waiting
        if not self._waiting_at_panel:
            self.get_logger().warn("Timer callback called but not waiting at panel, ignoring...")
            return
        
        self._waiting_at_panel = False
        if self._wait_timer:
            self._wait_timer.cancel()
            self._wait_timer = None
        
        self.get_logger().info("3-second wait completed, continuing to next waypoint...")
        # Now proceed to next waypoint
        self.idx += 1
        if self.idx < len(self.waypoints):
            self._publish_current_goal()
        else:
            self.get_logger().info(f"✅ Panel Route {self.current_route} completed!")
            # Move to next route
            if not self._start_next_route():
                # All routes completed
                pass

    def _reached_cb(self, msg: Bool):
        if not msg.data:
            return
        
        # Prevent processing if we're already waiting at a panel
        if self._waiting_at_panel:
            self.get_logger().debug("Goal reached callback received while waiting at panel, ignoring...")
            return
        
        self._last_goal_msg = None  # stop republishing current
        
        # Check if we just reached the panel position waypoint (wait point)
        # Panel positions are at index 2 for routes 1 and 2, index 1 for routes 3 and 4
        wait_indices = {1: 2, 2: 2, 3: 1, 4: 1}
        wait_idx = wait_indices.get(self.current_route, -1)
        
        if self.idx == wait_idx:
            # Prevent multiple timers if callback is called multiple times
            if self._waiting_at_panel:
                return  # Already waiting, ignore duplicate call
            
            x, z = self.waypoints[self.idx]
            self.get_logger().info(f"Reached panel waypoint ({x:.1f}, {z:.1f}) on Route {self.current_route}. Waiting 3 seconds...")
            self._waiting_at_panel = True
            
            # Cancel any existing timer before creating a new one
            if self._wait_timer:
                self._wait_timer.cancel()
            
            # Wait 3 seconds then continue (non-blocking using timer)
            # Commented out: Enter key wait
            # self._waiting_for_input = True
            # self._input_thread = threading.Thread(target=self._wait_for_enter, daemon=True)
            # self._input_thread.start()
            self._wait_timer = self.create_timer(3.0, self._continue_after_wait)
        else:
            # Normal progression for other waypoints
            self.idx += 1
            if self.idx < len(self.waypoints):
                self._publish_current_goal()
            else:
                self.get_logger().info(f"✅ Panel Route {self.current_route} completed!")
                # Move to next route
                if not self._start_next_route():
                    # All routes completed
                    pass

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
