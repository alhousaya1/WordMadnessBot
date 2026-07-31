"""Bounded interpolation and velocity smoothing for normalized paths."""

from itertools import pairwise

from word_madness_bot.domain.models import NormalizedPoint


class PathSmoother:
    """Add intermediate points without moving or omitting required letter anchors."""

    def smooth(
        self,
        anchors: tuple[NormalizedPoint, ...],
        *,
        interpolation_points: int,
        smoothing_strength: float,
    ) -> tuple[NormalizedPoint, ...]:
        """Interpolate each segment using a configurable linear/smoothstep time blend."""

        if len(anchors) < 2:
            raise ValueError("path smoothing requires at least two anchors")
        if interpolation_points < 0:
            raise ValueError("interpolation point count cannot be negative")
        if not 0.0 <= smoothing_strength <= 1.0:
            raise ValueError("smoothing strength must be between zero and one")

        points: list[NormalizedPoint] = [anchors[0]]
        samples_per_segment = interpolation_points + 1
        for start, end in pairwise(anchors):
            for sample in range(1, samples_per_segment + 1):
                if sample == samples_per_segment:
                    points.append(end)
                    continue
                linear_t = sample / samples_per_segment
                smooth_t = linear_t * linear_t * (3.0 - 2.0 * linear_t)
                t = linear_t * (1.0 - smoothing_strength) + smooth_t * smoothing_strength
                points.append(
                    NormalizedPoint(
                        x=start.x + (end.x - start.x) * t,
                        y=start.y + (end.y - start.y) * t,
                    )
                )
        return tuple(points)
