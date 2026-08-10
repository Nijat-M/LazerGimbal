import threading
import unittest

from core.control.manual_aim_controller import ManualAimController
from core.gimbal_controller import GimbalController
from core.serial_thread import SerialThread


class FakeSerialThread:
    def __init__(self) -> None:
        self.realtime_commands = []
        self.stop_count = 0
        self.center_count = 0
        self.connected = True

    def is_connected(self) -> bool:
        return self.connected

    def send_realtime_command(self, command: str) -> None:
        self.realtime_commands.append(command)

    def send_stop_command(self) -> None:
        self.stop_count += 1

    def send_center_command(self) -> None:
        self.center_count += 1

    def send_command(self, command: str) -> None:
        pass


class ManualAimControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aim = ManualAimController(
            sensitivity=0.1,
            yaw_limits=(-1.0, 1.0),
            pitch_limits=(-0.5, 0.5),
        )

    def test_accumulates_relative_mouse_movement(self) -> None:
        target = self.aim.add_mouse_delta(5, -2)
        self.assertEqual(target, (0.5, 0.2))
        self.assertEqual(
            self.aim.consume_angle_delta(max_abs_delta=1.0, min_abs_delta=0.01),
            (0.5, 0.2),
        )
        self.assertEqual(
            self.aim.consume_angle_delta(max_abs_delta=1.0, min_abs_delta=0.01),
            (0.0, 0.0),
        )

    def test_applies_soft_limits_to_target_and_output(self) -> None:
        self.aim.add_mouse_delta(100, -100)
        self.assertEqual(self.aim.get_target(), (1.0, 0.5))
        self.assertEqual(
            self.aim.consume_angle_delta(max_abs_delta=1.0, min_abs_delta=0.01),
            (1.0, 0.5),
        )

        self.aim.add_mouse_delta(10, -10)
        self.assertEqual(
            self.aim.consume_angle_delta(max_abs_delta=1.0, min_abs_delta=0.01),
            (0.0, 0.0),
        )

    def test_retains_capped_and_sub_quantum_remainders(self) -> None:
        aim = ManualAimController(0.01, (-20.0, 20.0), (-20.0, 20.0))
        aim.add_mouse_delta(1, 0)
        self.assertEqual(
            aim.consume_angle_delta(max_abs_delta=2.4, min_abs_delta=0.02),
            (0.0, 0.0),
        )
        aim.add_mouse_delta(1, 0)
        yaw, _ = aim.consume_angle_delta(max_abs_delta=2.4, min_abs_delta=0.02)
        self.assertAlmostEqual(yaw, 0.02)

        aim.add_mouse_delta(1000, 0)
        yaw, _ = aim.consume_angle_delta(max_abs_delta=2.4, min_abs_delta=0.02)
        self.assertAlmostEqual(yaw, 2.4)
        yaw, _ = aim.consume_angle_delta(max_abs_delta=2.4, min_abs_delta=0.02)
        self.assertAlmostEqual(yaw, 2.4)

    def test_discard_pending_rolls_back_unsent_target(self) -> None:
        self.aim.add_mouse_delta(5, -2)
        self.assertEqual(self.aim.discard_pending(), (0.0, 0.0))

    def test_rejects_non_positive_sensitivity(self) -> None:
        with self.assertRaises(ValueError):
            self.aim.set_sensitivity(0.0)


class SerialRealtimeQueueTests(unittest.TestCase):
    def test_realtime_command_is_latest_wins_and_stop_clears_it(self) -> None:
        transport = SerialThread()
        transport.send_realtime_command("<1,0,0>")
        transport.send_realtime_command("<2,0,0>")

        with transport._latest_lock:
            self.assertEqual(transport._latest_realtime_command, "<2,0,0>\n")

        transport.send_stop_command()
        with transport._latest_lock:
            self.assertIsNone(transport._latest_realtime_command)
        self.assertEqual(transport.urgent_queue.get_nowait(), "!STOP\n")

        transport.send_realtime_command("<3,0,0>")
        transport.send_center_command()
        with transport._latest_lock:
            self.assertIsNone(transport._latest_realtime_command)
        self.assertEqual(transport.urgent_queue.get_nowait(), "!CENTER\n")


class BlockingFakeSerialThread(FakeSerialThread):
    def __init__(self) -> None:
        super().__init__()
        self.send_started = threading.Event()
        self.allow_send = threading.Event()
        self.operations = []

    def send_realtime_command(self, command: str) -> None:
        self.send_started.set()
        self.allow_send.wait(timeout=1.0)
        self.operations.append("motion")
        super().send_realtime_command(command)

    def send_stop_command(self) -> None:
        self.operations.append("stop")
        super().send_stop_command()


class GimbalMouseIntegrationTests(unittest.TestCase):
    def test_mouse_delta_generates_one_bounded_realtime_command(self) -> None:
        transport = FakeSerialThread()
        controller = GimbalController(transport)
        controller.is_running = False
        controller.control_thread.join(timeout=1.0)
        controller.is_running = True
        controller.set_invert(False, False)
        controller.set_manual_mouse_mode(True)
        controller.set_mouse_capture_active(True)

        controller.handle_mouse_delta(10, -5)
        controller.control_loop()

        self.assertEqual(transport.realtime_commands[-1], "<40,-20,0>\n")

        stops_before_idle_tick = transport.stop_count
        controller.control_loop()
        self.assertEqual(transport.stop_count, stops_before_idle_tick + 1)

    def test_vision_samples_are_ignored_until_camera_is_ready(self) -> None:
        transport = FakeSerialThread()
        controller = GimbalController(transport)
        controller.is_running = False
        controller.control_thread.join(timeout=1.0)

        controller.handle_target_position(400, 300)
        self.assertEqual((controller.current_error_x, controller.current_error_y), (0, 0))

        controller.set_visual_input_enabled(True)
        controller.handle_target_position(400, 300)
        self.assertNotEqual((controller.current_error_x, controller.current_error_y), (0, 0))

    def test_concurrent_stop_is_ordered_after_inflight_motion(self) -> None:
        transport = BlockingFakeSerialThread()
        controller = GimbalController(transport)
        controller.is_running = False
        controller.control_thread.join(timeout=1.0)
        controller.is_running = True
        controller.set_invert(False, False)
        controller.set_manual_mouse_mode(True)
        controller.set_mouse_capture_active(True)
        controller.handle_mouse_delta(10, 0)
        transport.operations.clear()

        control_thread = threading.Thread(target=controller.control_loop)
        control_thread.start()
        self.assertTrue(transport.send_started.wait(timeout=1.0))

        stop_thread = threading.Thread(target=controller.stop)
        stop_thread.start()
        transport.allow_send.set()
        control_thread.join(timeout=1.0)
        stop_thread.join(timeout=1.0)

        self.assertEqual(transport.operations, ["motion", "stop"])


if __name__ == "__main__":
    unittest.main()
