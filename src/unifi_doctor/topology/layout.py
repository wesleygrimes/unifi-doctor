"""Spring-force layout engine — converts pairwise AP distances to 2D coordinates."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from unifi_doctor.models.types import Topology


@dataclass
class NodePosition:
    mac: str
    name: str
    x: float = 0.0
    y: float = 0.0


@dataclass
class LayoutResult:
    positions: list[NodePosition] = field(default_factory=list)


def compute_layout(topology: Topology, *, iterations: int = 500, seed: int = 42) -> LayoutResult:
    """Compute 2D positions for APs using spring-force simulation.

    Uses a Fruchterman-Reingold style algorithm:
    - Connected pairs attract/repel toward their target distance
    - All pairs repel to avoid overlap
    - Temperature decays over iterations to converge
    """
    placements = topology.placements
    n = len(placements)

    # Edge cases
    if n == 0:
        return LayoutResult()

    if n == 1:
        return LayoutResult(positions=[NodePosition(mac=placements[0].mac, name=placements[0].name, x=0.5, y=0.5)])

    if n == 2:
        return LayoutResult(
            positions=[
                NodePosition(mac=placements[0].mac, name=placements[0].name, x=0.2, y=0.5),
                NodePosition(mac=placements[1].mac, name=placements[1].name, x=0.8, y=0.5),
            ]
        )

    # Build distance lookup from links
    dist_lookup: dict[tuple[str, str], float] = {}
    for link in topology.links:
        key = tuple(sorted([link.ap1_mac, link.ap2_mac]))
        dist_lookup[key] = link.distance_ft  # type: ignore[assignment]

    # Initialize positions randomly (seeded for determinism)
    rng = random.Random(seed)
    positions: list[list[float]] = [[rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9)] for _ in range(n)]

    # Simulation parameters
    area = 1.0
    k = math.sqrt(area / n)  # optimal distance between nodes
    t = 0.1  # initial temperature (max displacement per iteration)

    for iteration in range(iterations):
        # Compute displacements
        disp = [[0.0, 0.0] for _ in range(n)]

        # Repulsive forces between all pairs
        for i in range(n):
            for j in range(i + 1, n):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 1e-6:
                    dist = 1e-6

                # Repulsive force: k^2 / dist
                force = (k * k) / dist
                fx = (dx / dist) * force
                fy = (dy / dist) * force

                disp[i][0] += fx
                disp[i][1] += fy
                disp[j][0] -= fx
                disp[j][1] -= fy

        # Attractive forces on connected pairs (spring toward target distance)
        if dist_lookup:
            # Normalize target distances to layout scale
            max_dist = max(dist_lookup.values()) if dist_lookup else 1.0
            if max_dist < 1e-6:
                max_dist = 1.0

            for (mac_a, mac_b), target_ft in dist_lookup.items():
                # Find indices
                idx_a = idx_b = -1
                for idx, p in enumerate(placements):
                    if p.mac == mac_a:
                        idx_a = idx
                    elif p.mac == mac_b:
                        idx_b = idx
                if idx_a < 0 or idx_b < 0:
                    continue

                dx = positions[idx_a][0] - positions[idx_b][0]
                dy = positions[idx_a][1] - positions[idx_b][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 1e-6:
                    dist = 1e-6

                # Target distance normalized to ~0.7 of layout area
                target_norm = (target_ft / max_dist) * 0.7

                # Spring force: proportional to (dist - target)
                force = (dist - target_norm) / 2.0
                fx = (dx / dist) * force
                fy = (dy / dist) * force

                disp[idx_a][0] -= fx
                disp[idx_a][1] -= fy
                disp[idx_b][0] += fx
                disp[idx_b][1] += fy

        # Apply displacements, clamped by temperature
        for i in range(n):
            dx = disp[i][0]
            dy = disp[i][1]
            mag = math.sqrt(dx * dx + dy * dy)
            if mag > 1e-6:
                scale = min(mag, t) / mag
                positions[i][0] += dx * scale
                positions[i][1] += dy * scale

        # Cool down temperature
        t *= 1.0 - (iteration + 1) / (iterations + 1)
        if t < 1e-6:
            t = 1e-6

    # Normalize positions to [0, 1]
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x if max_x - min_x > 1e-6 else 1.0
    range_y = max_y - min_y if max_y - min_y > 1e-6 else 1.0

    result_positions = []
    for i, placement in enumerate(placements):
        nx = (positions[i][0] - min_x) / range_x
        ny = (positions[i][1] - min_y) / range_y
        # Add margin
        nx = 0.05 + nx * 0.9
        ny = 0.05 + ny * 0.9
        result_positions.append(NodePosition(mac=placement.mac, name=placement.name, x=nx, y=ny))

    return LayoutResult(positions=result_positions)
