#!/usr/bin/env python3
import time
import struct
import atexit
import signal
from dataclasses import dataclass
from typing import Optional

import numpy as np
import serial
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool

# ==================== Hardcoded control & I/O configuration ====================

RATE_HZ = 30.0
LOCALIZATION_TOPIC = "/localization/odom"
OPENVINS_TOPIC = "/ov_msckf/odomimu"  # Changed from /ov_msckf/poseimu to /ov_msckf/odomimu (Odometry)
USE_Z_AS_FORWARD = True  # forward is pose.position.z (+z = forward)

# Camera to car center offset (in camera frame: x, z)
# Car center = Camera - (0, 0.1) means car is 0.1m behind camera along z-axis
CAMERA_TO_CAR_OFFSET_X = 0.0   # meters: lateral offset
CAMERA_TO_CAR_OFFSET_Z = 0.1   # meters: forward offset (car behind camera)

# Convention: right = +x, left = -x, forward/up = +z, back/down = -z

# Watchdog + goal tolerances
STALE_TIMEOUT = 2.0   # seconds without odom → STOP
X_EPS = 0.04          # meters: align X within this tolerance first (was 0.10)
Z_EPS = 0.04         # meters: then drive Z within this tolerance (was 0.10)
YAW_EPS = 0.05        # radians: align yaw within this tolerance (≈8.6 degrees)
ARRIVAL_DWELL = 0.20  # seconds we must remain inside the goal band

# ==================== Surface Configuration ====================
# Select surface: "original" or "carpet"
SURFACE = "carpet"  # Change to "original" for original surface

# Surface-specific parameter sets
SURFACE_CONFIGS = {
    "original": {
        # PD gains (tuned so ~0.5 m error → ~100 motor units)
        "PID_X": (200.0, 0.0, 20.0),      # kp, ki, kd for X (ki kept 0 for crisp control)
        "PID_Z": (200.0, 0.0, 20.0),      # kp, ki, kd for Z
        "PID_YAW": (100.0, 0.0, 25.0),    # kp, ki, kd for yaw rotation
        "PID_CLAMP": 300.0,                # pre-mix clamp (Arduino clamps to ±400)
        "AXIS_MIN_CMD": 40.0,              # minimum command to overcome stiction
    },
    "carpet": {
        # Higher gains and minimum commands to overcome carpet friction
        "PID_X": (350.0, 0.0, 30.0),      # increased kp and kd for carpet
        "PID_Z": (350.0, 0.0, 30.0),      # increased kp and kd for carpet
        "PID_YAW": (150.0, 0.0, 35.0),    # increased kp and kd for carpet
        "PID_CLAMP": 350.0,                # higher clamp for carpet
        "AXIS_MIN_CMD": 70.0,              # much higher minimum to overcome carpet stiction
    },
}

# Get current surface configuration
if SURFACE not in SURFACE_CONFIGS:
    raise ValueError(f"Unknown surface '{SURFACE}'. Must be one of: {list(SURFACE_CONFIGS.keys())}")

_config = SURFACE_CONFIGS[SURFACE]
PID_X = _config["PID_X"]
PID_Z = _config["PID_Z"]
PID_YAW = _config["PID_YAW"]
PID_CLAMP = _config["PID_CLAMP"]
AXIS_MIN_CMD = _config["AXIS_MIN_CMD"]

SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD = 115200

# ========================= BotBoarduino USB Packet ============================

PKT_HDR0 = 0xAA
PKT_HDR1 = 0x55
PKT_VER  = 0x01
PKT_LEN  = 8   # 4 x int16

def build_packet(fl: int, fr: int, bl: int, br: int) -> bytes:
    def clamp400(x: float) -> int:
        xi = int(round(x))
        return max(-400, min(400, xi))
    fl, fr, bl, br = map(clamp400, (fl, fr, bl, br))
    payload = struct.pack('<hhhh', fl, fr, bl, br)
    csum = (PKT_VER + PKT_LEN + sum(payload)) & 0xFF
    return bytes([PKT_HDR0, PKT_HDR1, PKT_VER, PKT_LEN]) + payload + bytes([csum])

class SerialTransport:
    def __init__(self, port: str = SERIAL_PORT, baud: int = SERIAL_BAUD):
        self._serial = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
            write_timeout=0.05,
            exclusive=True,
        )
        time.sleep(2.0)  # allow 328P reset after DTR
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def send_offsets(self, fl: float, fr: float, bl: float, br: float):
        self._serial.write(build_packet(fl, fr, bl, br))
        self._serial.flush()

    def stop(self):
        try:
            self.send_offsets(0, 0, 0, 0)
        except Exception:
            pass

    def close(self):
        try:
            self._serial.close()
        except Exception:
            pass

# ========================== Quaternion to Euler ==============================

def quaternion_to_euler(w: float, x: float, y: float, z: float) -> tuple[float, float, float]:
    """
    Convert quaternion to Euler angles (roll, pitch, yaw).
    Returns (roll, pitch, yaw) in radians.
    """
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)  # use 90 degrees if out of range
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw

def normalize_angle(angle: float) -> float:
    """Normalize angle to [-π, π] range using modulo for stable wrapping."""
    return ((angle + math.pi) % (2 * math.pi)) - math.pi

# ================================== PID =======================================

@dataclass
class PID:
    kp: float
    ki: float
    kd: float
    clamp: float
    last_err: Optional[float] = None

    def reset(self):
        self.last_err = None

    def update(self, err: float, dt: float) -> float:
        der = 0.0 if self.last_err is None else (err - self.last_err) / max(dt, 1e-6)
        self.last_err = err
        out = self.kp * err + self.kd * der  # ki=0 (crisp)
        return float(np.clip(out, -self.clamp, self.clamp))

# ============================ Crab PID Controller =============================

class CrabPIDController(Node):
    """
    Simultaneous control: All axes (x, z, yaw) controlled at once.
    Wheel mix matches the proven teleop mapping with rotation:
        Map x:=uf (forward), y:=ux (lateral), r:=ur (rotation)
        fl = uf + ux + ur
        fr = uf - ux - ur
        bl = uf - ux + ur
        br = uf + ux - ur
    """

    def __init__(self):
        super().__init__("crab_pid_controller")
        self.use_z_as_forward = USE_Z_AS_FORWARD
        self.stale_timeout = STALE_TIMEOUT

        # Log surface configuration
        self.get_logger().info(
            f"Surface configuration: {SURFACE} | "
            f"PID_X={PID_X}, PID_Z={PID_Z}, PID_YAW={PID_YAW}, "
            f"PID_CLAMP={PID_CLAMP}, AXIS_MIN_CMD={AXIS_MIN_CMD}"
        )

        # Pose/goal state
        self.have_pose = False
        self.pose_x = 0.0
        self.pose_z = 0.0
        self.pose_yaw = 0.0
        self.last_pose_walltime = time.time()
        self.goal_x: Optional[float] = None
        self.goal_z: Optional[float] = None
        self.goal_yaw: Optional[float] = None
        
        # Initial rotation tracking
        self.initial_yaw: Optional[float] = None
        self.initial_yaw_set = False

        # For stable arrival detection
        self._in_band_since: Optional[float] = None

        # PIDs
        self.pid_x = PID(*PID_X, PID_CLAMP)
        self.pid_z = PID(*PID_Z, PID_CLAMP)
        self.pid_yaw = PID(*PID_YAW, PID_CLAMP)

        # Serial
        try:
            self.tx = SerialTransport(port=SERIAL_PORT, baud=SERIAL_BAUD)
            self.get_logger().info(f"Opened serial {SERIAL_PORT} @ {SERIAL_BAUD}")
        except Exception as e:
            self.get_logger().fatal(f"Serial open failed: {e}")
            raise

        # ROS I/O
        self.odom_sub = self.create_subscription(Odometry, LOCALIZATION_TOPIC, self._odom_cb, qos_profile_sensor_data)
        self.openvins_sub = self.create_subscription(Odometry, OPENVINS_TOPIC, self._openvins_cb, qos_profile_sensor_data)
        self.goal_sub = self.create_subscription(PoseStamped, "/planner/goal", self._goal_cb, 10)
        self.reached_pub = self.create_publisher(Bool, "/controller/goal_reached", 10)
        
        # Log subscription info for debugging
        self.get_logger().info(f"📡 Subscribed to OpenVINS topic: {OPENVINS_TOPIC}")
        self.get_logger().info(f"📡 Subscribed to localization topic: {LOCALIZATION_TOPIC}")
        self.get_logger().info(f"📡 Subscribed to goal topic: /planner/goal")
        self.get_logger().info(f"📡 Publishing to: /controller/goal_reached")

        # Control loop
        self.timer = self.create_timer(1.0 / RATE_HZ, self._step)
        self._next_log_time = 0.0  # throttle prints to ~5 Hz

        # Clean shutdowns (Ctrl-C / systemd stop)
        atexit.register(self._shutdown)
        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    # ------------------------------- Callbacks --------------------------------

    def _goal_cb(self, msg: PoseStamped):
        new_x = float(msg.pose.position.x)
        new_z = float(msg.pose.position.z if self.use_z_as_forward else msg.pose.position.y)
        
        # Always use initial yaw as target rotation (ignore goal orientation)
        if self.initial_yaw is not None:
            new_yaw = self.initial_yaw
        else:
            # Fallback: extract yaw from goal orientation if initial yaw not set yet
            q = msg.pose.orientation
            _, _, new_yaw = quaternion_to_euler(q.w, q.x, q.y, q.z)

        # Treat as new if position coordinates change (with tolerance)
        is_new = (
            self.goal_x is None or
            self.goal_z is None or
            abs(new_x - (self.goal_x or 0.0)) > 1e-6 or
            abs(new_z - (self.goal_z or 0.0)) > 1e-6
        )

        self.goal_x = new_x
        self.goal_z = new_z
        self.goal_yaw = new_yaw  # Always use initial yaw

        if is_new:
            self.pid_x.reset()
            self.pid_z.reset()
            self.pid_yaw.reset()
            self._in_band_since = None
            axis = "z" if self.use_z_as_forward else "y"
            self.get_logger().info(
                f"Got new goal: (x={self.goal_x:.3f}, {axis}={self.goal_z:.3f}, yaw={self.goal_yaw:.3f} [initial]); simultaneous control"
            )
        else:
            axis = "z" if self.use_z_as_forward else "y"
            self.get_logger().info(
                f"Got rebroadcasted goal: (x={self.goal_x:.3f}, {axis}={self.goal_z:.3f}, yaw={self.goal_yaw:.3f} [initial])"
            )

    def _odom_cb(self, msg: Odometry):
        # Get camera pose from localization
        camera_x = float(msg.pose.pose.position.x)
        camera_z = float(msg.pose.pose.position.z if self.use_z_as_forward else msg.pose.pose.position.y)
        
        # Convert camera pose to car center pose: car = camera - (0, 0.1)
        self.pose_x = camera_x - CAMERA_TO_CAR_OFFSET_X
        self.pose_z = camera_z - CAMERA_TO_CAR_OFFSET_Z
        
        self.have_pose = True
        self.last_pose_walltime = time.time()

    def _openvins_cb(self, msg: Odometry):
        """Handle OpenVINS odometry messages for yaw estimation."""
        try:
            # Extract yaw from OpenVINS orientation (Odometry message)
            q = msg.pose.pose.orientation
            _, _, self.pose_yaw = quaternion_to_euler(q.w, q.x, q.y, q.z)
            
            # Save initial yaw on first pose received
            if not self.initial_yaw_set:
                self.initial_yaw = self.pose_yaw
                self.goal_yaw = self.initial_yaw  # Set target to initial rotation
                self.initial_yaw_set = True
                self.get_logger().info(f"🎯 Initial yaw saved: {self.initial_yaw:.3f} rad ({math.degrees(self.initial_yaw):.1f}°) - will maintain this heading")
            
            self.have_pose = True
            self.last_pose_walltime = time.time()
        except Exception as e:
            self.get_logger().error(f"Error processing OpenVINS message: {e}")

    # -------------------------------- Helpers ---------------------------------

    def _stale(self) -> bool:
        return (time.time() - self.last_pose_walltime) > self.stale_timeout

    def _inside_goal_band(self) -> bool:
        if self.goal_x is None or self.goal_z is None or self.goal_yaw is None:
            return False
        dx = abs(self.goal_x - self.pose_x)
        dz = abs(self.goal_z - self.pose_z)
        dyaw = abs(normalize_angle(self.goal_yaw - self.pose_yaw))
        return (dx <= X_EPS) and (dz <= Z_EPS) and (dyaw <= YAW_EPS)

    def _apply_deadband(self, axis_cmd: float, err_abs: float, eps: float) -> float:
        """Guarantee a minimum command whenever we're still outside the tolerance.
        When inside tolerance, apply smaller minimum to maintain position without oscillation."""
        if err_abs > eps:
            # Outside tolerance: apply full minimum to overcome stiction
            if abs(axis_cmd) < AXIS_MIN_CMD:
                return AXIS_MIN_CMD * (1.0 if axis_cmd >= 0 else -1.0)
        else:
            # Inside tolerance: apply smaller minimum (50% of full) to maintain position
            # This prevents oscillation while keeping enough control to prevent drift
            inside_min = AXIS_MIN_CMD * 0.35  # 20 units instead of 40
            if abs(axis_cmd) < inside_min and abs(axis_cmd) > 1e-6:
                # Only apply minimum if PID is actively trying to correct (non-zero command)
                return inside_min * (1.0 if axis_cmd >= 0 else -1.0)
            # If command is larger than minimum, use it directly (no scaling)
            # If command is truly zero, keep it zero
        return axis_cmd

    # ------------------------------ Control Loop ------------------------------

    def _step(self):
        # No goal → stop
        if self.goal_x is None or self.goal_z is None:
            self.tx.stop()
            # Log why we're idle (throttled)
            now = time.time()
            if now >= self._next_log_time:
                self.get_logger().warn(
                    f"[IDLE] Waiting for goal from /planner/goal. "
                    f"Check if demo_planner_node is running and publishing goals."
                )
                self._next_log_time = now + 2.0  # Log every 2 seconds
            return
            
        # If no initial yaw set yet, wait for it
        if not self.initial_yaw_set:
            self.tx.stop()
            # Log why we're idle (throttled)
            now = time.time()
            if now >= self._next_log_time:
                self.get_logger().warn(
                    f"[IDLE] Waiting for initial yaw from {OPENVINS_TOPIC}. "
                    f"Goal received (x={self.goal_x:.3f}, z={self.goal_z:.3f}), "
                    f"but OpenVINS pose not yet received."
                )
                self.get_logger().warn(
                    f"  Troubleshooting: Check if OpenVINS is publishing to {OPENVINS_TOPIC} "
                    f"with message type Odometry"
                )
                self.get_logger().warn(
                    f"  Run: ros2 topic list | grep ov_msckf"
                )
                self.get_logger().warn(
                    f"  Run: ros2 topic info {OPENVINS_TOPIC}"
                )
                self._next_log_time = now + 5.0  # Log every 5 seconds
            return

        # Stale/no localization → STOP + print last location
        if (not self.have_pose) or self._stale():
            self.tx.stop()
            axis = "z" if self.use_z_as_forward else "y"
            self.get_logger().warn(
                f"Localization stale/no-data → STOP. Last pose: (x={self.pose_x:.3f}, {axis}={self.pose_z:.3f}, yaw={self.pose_yaw:.3f})"
            )
            return

        # Stable-in-band arrival detection
        now = time.time()
        if self._inside_goal_band():
            if self._in_band_since is None:
                self._in_band_since = now
            if (now - self._in_band_since) >= ARRIVAL_DWELL:
                self.tx.stop()
                # Only publish once per goal (prevent duplicate messages)
                if self.goal_x is not None or self.goal_z is not None:
                    self.reached_pub.publish(Bool(data=True))
                    axis = "z" if self.use_z_as_forward else "y"
                    self.get_logger().info(
                        f"Goal reached (within {X_EPS:.2f} m, {YAW_EPS:.2f} rad) at pose: (x={self.pose_x:.3f}, {axis}={self.pose_z:.3f}, yaw={self.pose_yaw:.3f}). Motors stopped."
                    )
                self.goal_x = None
                self.goal_z = None
                # Keep goal_yaw as initial_yaw for next goal
                self._in_band_since = None
                return
        else:
            self._in_band_since = None

        dt = 1.0 / RATE_HZ

        # --------- Simultaneous control: All axes controlled at once ----------
        ex = self.goal_x - self.pose_x  # +ex => go RIGHT
        ez = self.goal_z - self.pose_z  # +ez => go FORWARD (+z)
        eyaw = normalize_angle(self.pose_yaw - self.goal_yaw)  # +eyaw => turn LEFT (flipped direction)

        # Compute PID for all axes simultaneously
        ux = self.pid_x.update(ex, dt)
        ux = self._apply_deadband(ux, abs(ex), X_EPS)
        
        uf = self.pid_z.update(ez, dt)
        uf = self._apply_deadband(uf, abs(ez), Z_EPS)
        
        ur = self.pid_yaw.update(eyaw, dt)
        ur = self._apply_deadband(ur, abs(eyaw), YAW_EPS)

        # Human-friendly terminal print (throttled), based on error signs
        if now >= self._next_log_time:
            # Determine primary actions based on largest error
            actions = []
            if abs(ex) > 0.01:
                actions.append("RIGHT" if ex > 0 else "LEFT")
            if abs(ez) > 0.01:
                actions.append("FORWARD" if ez > 0 else "BACKWARD")
            if abs(eyaw) > 0.01:
                actions.append("TURN_L" if eyaw > 0 else "TURN_R")
            action_str = "+".join(actions) if actions else "HOLD"
            
            eyaw_deg = math.degrees(eyaw)
            goal_yaw_deg = math.degrees(self.goal_yaw)
            pose_yaw_deg = math.degrees(self.pose_yaw)
            
            self.get_logger().info(
                f"[SIMULTANEOUS] pose=({self.pose_x:.3f}, {self.pose_z:.3f}, {pose_yaw_deg:.1f}°), "
                f"goal=({self.goal_x:.3f}, {self.goal_z:.3f}, {goal_yaw_deg:.1f}°), "
                f"errors: ex={ex:.3f}, ez={ez:.3f}, eyaw={eyaw:.3f} ({eyaw_deg:.1f}°)  |  action: {action_str}  |  "
                f"cmd: ux={ux:.1f}, uf={uf:.1f}, ur={ur:.1f}"
            )
            self._next_log_time = now + 0.2

        # ========================= SEND TO WHEELS =========================
        # Standard teleop-equivalent mix with rotation:
        #   x := uf (forward, +z), y := ux (lateral, +x), r := ur (rotation, +yaw)
        #   fl = uf + ux + ur
        #   fr = uf - ux - ur
        #   bl = uf - ux + ur
        #   br = uf + ux - ur
        fl = (uf) + (+ux) + (+ur)
        fr = (uf) + (-ux) + (-ur)
        bl = (uf) + (-ux) + (+ur)
        br = (uf) + (+ux) + (-ur)
        self.tx.send_offsets(fl, fr, bl, br)
        # ==================================================================

    # ------------------------------- Shutdown ---------------------------------

    def _handle_signal(self, *_):
        # Ensure motors stop, then shut ROS and exit the process cleanly
        try:
            self.tx.stop()
        except Exception:
            pass
        # Allow rclpy to break out of spin()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        # Exit the process so you don't get stuck after many ^C
        raise SystemExit(0)

    def _shutdown(self):
        try: self.tx.stop()
        except Exception: pass
        try: self.tx.close()
        except Exception: pass

# ================================== main ======================================

def main():
    rclpy.init()
    node = CrabPIDController()
    try:
        rclpy.spin(node)
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            rclpy.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()