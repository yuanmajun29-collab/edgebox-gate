"""``apps/energy`` 与 shared 之间的薄层（Blueprint 注册等）。"""

from edgebox.shared.energy_line.wave_energy_common import register_energy_blueprints

__all__ = ["register_energy_blueprints"]
