# SPDX-License-Identifier: GPL-3.0-or-later
"""The openEMS model of a model spec (spec 3.3, 5.8, 6.2): the CSX and the FDTD setup a worker runs. Property names
carry their role (C-16): `port_*` are openEMS's own port properties, `lumped_*` the grid's parts, and `metal`,
`substrate_*` and `mask_*` the rest."""
from __future__ import annotations

METAL_PRIORITY = 1000  # above every material's 10 + i


def _prism(prop: object, solid: dict, priority: int) -> None:
    """`solid` ({"x", "y", "z": [z0, z1]}) as a polygon of `prop` extruded in z from z0 to z1."""
    z0, z1 = solid["z"]
    prop.AddLinPoly([solid["x"], solid["y"]], "z", z0, z1 - z0, priority=priority)


def build_csx(spec: dict, excite: int, t_max: float) -> tuple[object, object]:
    """The ContinuousStructure and the openEMS object of `spec` (model_spec()), in mm, run up to `t_max` s with port
    `excite` (1-based) excited: EndCriteria 1e-15, Mur on all six sides, the spec's pulse and openEMS's own time step
    (W-1); each port a 50 Ω lumped port, or for kind "curve" a 50 Ω CurvePort (openEMS's one-edge lumped port joined
    to both ends by PEC curves, r3); each grid part a lumped element of whichever of R, C and L it sets, in parallel:
    LEtype is never set, so it is 0 (1 is unstable in 0.37). Points go to CSXCAD as [xs, ys]: it misreads an (N, 2)
    array silently. CSXCAD and openEMS are imported here only, so that only a worker loads them."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    fdtd = openEMS(EndCriteria=1e-15)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1e-3)
    for axis in "xyz":
        grid.SetLines(axis, spec["mesh"][axis])
    fdtd.SetBoundaryCond(["MUR"] * 6)
    pulse = spec["excitation"]
    fdtd.SetCustomExcite(pulse["expr"], pulse["f2"], pulse["f2"])
    fdtd.SetMaxTime(t_max)

    for m in spec["materials"]:
        material = csx.AddMaterial(m["name"], epsilon=m["eps"], kappa=m["kappa"])
        for solid in m["solids"]:
            _prism(material, solid, m["priority"])

    pec, metal = spec["metal"], csx.AddMetal("metal")
    for solid in (*pec["copper"], *pec["lid"]["walls"]):
        _prism(metal, solid, METAL_PRIORITY)
    if (plate := pec["lid"]["plate"]) is not None:
        metal.AddPolygon([plate["x"], plate["y"]], "z", plate["z"], priority=METAL_PRIORITY)
    for rod in pec["cylinders"]:
        (x, y), (z0, z1) = rod["at"], rod["z"]
        metal.AddCylinder([x, y, z0], [x, y, z1], rod["r"], priority=METAL_PRIORITY)
    for rod in pec["curves"]:
        (x, y), (z0, z1) = rod["at"], rod["z"]
        metal.AddCurve([[x, x], [y, y], [z0, z1]])

    for k, port in enumerate(spec["ports"], 1):
        on = 1 if k == excite else 0
        if port["kind"] == "curve":
            fdtd.AddCurvePort(k, 50, port["start"], port["stop"], excite=on)
        else:
            fdtd.AddLumpedPort(k, 50, port["start"], port["stop"], port["dir"], excite=on)
    for i, part in enumerate(spec["grid"]):
        value = {key: part[key] for key in ("R", "C", "L") if part.get(key) is not None}
        element = csx.AddLumpedElement(f"lumped_{i}", ny="xyz".index(part["dir"]), caps=True, **value)
        element.AddBox(part["start"], part["stop"])
    return csx, fdtd
