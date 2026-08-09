# -*- coding: utf-8 -*-
"""Thread-safe mouse aiming state shared by GUI and control threads."""

from __future__ import annotations

import threading


class ManualAimController:
    """Convert relative mouse movement into a bounded virtual aim target."""

    def __init__(
        self,
        sensitivity: float,
        yaw_limits: tuple[float, float],
        pitch_limits: tuple[float, float],
    ) -> None:
        self._lock = threading.Lock()
        self._sensitivity = sensitivity
        self._yaw_limits = yaw_limits
        self._pitch_limits = pitch_limits
        self._target_yaw = 0.0
        self._target_pitch = 0.0
        self._pending_yaw_delta = 0.0
        self._pending_pitch_delta = 0.0

    def set_sensitivity(self, sensitivity: float) -> None:
        if sensitivity <= 0:
            raise ValueError("Mouse sensitivity must be positive")
        with self._lock:
            self._sensitivity = sensitivity

    def get_sensitivity(self) -> float:
        with self._lock:
            return self._sensitivity

    def add_mouse_delta(self, dx: int, dy: int) -> tuple[float, float]:
        """Apply FPS-style relative mouse movement and return the new target."""
        with self._lock:
            requested_yaw = self._target_yaw + dx * self._sensitivity
            requested_pitch = self._target_pitch - dy * self._sensitivity

            new_yaw = self._clamp(requested_yaw, self._yaw_limits)
            new_pitch = self._clamp(requested_pitch, self._pitch_limits)

            self._pending_yaw_delta += new_yaw - self._target_yaw
            self._pending_pitch_delta += new_pitch - self._target_pitch
            self._target_yaw = new_yaw
            self._target_pitch = new_pitch
            return self._target_yaw, self._target_pitch

    def consume_angle_delta(
        self,
        max_abs_delta: float,
        min_abs_delta: float,
    ) -> tuple[float, float]:
        """Consume a representable bounded increment and retain the remainder."""
        if max_abs_delta <= 0 or min_abs_delta <= 0:
            raise ValueError("Delta limits must be positive")
        with self._lock:
            yaw_delta = self._select_delta(
                self._pending_yaw_delta, max_abs_delta, min_abs_delta
            )
            pitch_delta = self._select_delta(
                self._pending_pitch_delta, max_abs_delta, min_abs_delta
            )
            self._pending_yaw_delta -= yaw_delta
            self._pending_pitch_delta -= pitch_delta
            return yaw_delta, pitch_delta

    def discard_pending(self) -> tuple[float, float]:
        """Cancel unsent movement so the virtual target stays synchronized."""
        with self._lock:
            self._target_yaw = self._clamp(
                self._target_yaw - self._pending_yaw_delta, self._yaw_limits
            )
            self._target_pitch = self._clamp(
                self._target_pitch - self._pending_pitch_delta, self._pitch_limits
            )
            self._pending_yaw_delta = 0.0
            self._pending_pitch_delta = 0.0
            return self._target_yaw, self._target_pitch

    def reset_target(self) -> tuple[float, float]:
        with self._lock:
            self._target_yaw = 0.0
            self._target_pitch = 0.0
            self._pending_yaw_delta = 0.0
            self._pending_pitch_delta = 0.0
            return self._target_yaw, self._target_pitch

    def get_target(self) -> tuple[float, float]:
        with self._lock:
            return self._target_yaw, self._target_pitch

    @staticmethod
    def _select_delta(value: float, maximum: float, minimum: float) -> float:
        bounded = max(-maximum, min(maximum, value))
        return bounded if abs(bounded) >= minimum else 0.0

    @staticmethod
    def _clamp(value: float, limits: tuple[float, float]) -> float:
        return max(limits[0], min(limits[1], value))
