# SPDX-License-Identifier: GPL-3.0-or-later
"""The openEMS model of a model spec (spec 3.3, 5.8, 6.2): the CSX and the FDTD setup a worker runs. Property names
carry their role (C-16): `port_*` are openEMS's own port properties, `lumped_*` the grid's parts, and `metal`,
`substrate_*` and `mask_*` the rest; a P0 harness's probes keep the names it gives them (D-13)."""
from __future__ import annotations

import math

METAL_PRIORITY = 1000  # above every material's 10 + i
PML_CELLS = 8  # PML_8's 8 outermost cells on each face (design 5.2)
BOUNDARY = {None: "MUR", "pml_8": f"PML_{PML_CELLS}"}  # the spec's "boundary"; absent in every v1 spec
NF2FF_MAX = 11  # the far-field frequencies a box records, at most (design 5.5)
EMISSION_NF2FF_MAX = 64  # an emission spec's: its harmonics and the 100 MHz grid (Stage 5 design 5.8, BC3)


def _prism(prop: object, solid: dict, priority: int, sheet: bool = False) -> None:
    """`solid` ({"x", "y", "z": [z0, z1]}) as a polygon of `prop` extruded in z from z0 to z1, or, with `sheet` (the
    antenna-only spec key "copper": "sheet", Stage 3 design 5.3) and z0 == z1, a polygon in the plane z = z0."""
    z0, z1 = solid["z"]
    if sheet and z0 == z1:
        prop.AddPolygon([solid["x"], solid["y"]], "z", z0, priority=priority)
    else:
        prop.AddLinPoly([solid["x"], solid["y"]], "z", z0, z1 - z0, priority=priority)


def build_csx(spec: dict, excite: int, t_max: float) -> tuple[object, object, object | None]:
    """The ContinuousStructure, the openEMS object and the far-field box of `spec` (model_spec()), in mm, run up to
    `t_max` s with port `excite` (1-based) excited: EndCriteria 1e-15, Mur on all six sides (PML_8 on all six when the
    antenna-only key "boundary" is "pml_8"), the spec's pulse and openEMS's own time step (W-1); each port a lumped
    port, or for kind "curve" a CurvePort (openEMS's one-edge lumped port joined to both ends by PEC curves, r3), of
    50 Ω, or of the port's "R" (an emission spec's termination, Stage 5 design 5.6); after the ports, each entry of the
    optional `spec["probes"]` ({"name", "type" (0 voltage, 1 current), "weight", "norm_dir" (optional), "start",
    "stop"}) an openEMS probe box, whose file the job leaves in its folder:
    the P0 harnesses' probes, which the product never writes (D-13); each grid part a lumped element of whichever of
    R, C and L it sets, in parallel: LEtype is never set, so it is 0 (1 is unstable in 0.37). The far-field box is None
    without the antenna-only key "nf2ff" ({"f_hz": [f0, …], "center": [x, y, z] (the transform's), "box": [start,
    stop] (optional)}, in Hz and mm); with it, the box records the far field in the frequency domain at "f_hz" (1 to
    NF2FF_MAX, or EMISSION_NF2FF_MAX under an emission pulse, "emission": true; each from f1 to f2), over-sampled 4
    times, on all six faces with no mirror, at openEMS's own placement (one line inside the PML) or at "box". The
    emission-only key "near_field" ({"start", "stop", "f_hz"}, Stage 5 design 5.8) adds a dump of H in the frequency
    domain at "f_hz" (dump type 11, an HDF5 file) over its plane, over-sampled 4 times as the box is. Points go to
    CSXCAD as [xs, ys]: it misreads an (N, 2) array silently.
    CSXCAD and openEMS are imported here only, so that only a worker loads them. Under the antenna-only key "copper":
    "sheet", a material's or the metal's solid of no thickness is a polygon in its plane (_prism). A material with the
    SI-only key "debye" ({"eps_inf", "delta", "f_relax_hz"}, Stage 4 design 5.3) is CSXCAD's CSPropDebyeMaterial, each
    pole's relaxation time 1/(2π·f_relax); its κ is ignored. openEMS 0.37 puts each pole on an edge at the edge's own
    point, over its whole area (operator_ext_debyematerial.cpp), where the static ε is averaged over the quarter cells,
    so the edges on a Debye substrate's top face carry its full Δε over dual cells half in air: a stated limit gate
    P4-D isolates. A "debye" whose two lists differ in length raises ValueError."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    fdtd = openEMS(EndCriteria=1e-15)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1e-3)
    for axis in "xyz":
        grid.SetLines(axis, spec["mesh"][axis])
    fdtd.SetBoundaryCond([BOUNDARY[spec.get("boundary")]] * 6)
    pulse = spec["excitation"]
    fdtd.SetCustomExcite(pulse["expr"], pulse["f2"], pulse["f2"])
    fdtd.SetMaxTime(t_max)

    sheet = spec.get("copper") == "sheet"
    for m in spec["materials"]:
        if (db := m.get("debye")) is not None:
            from CSXCAD.CSProperties import CSPropDebyeMaterial

            material = CSPropDebyeMaterial(csx.GetParameterSet(), order=len(db["delta"]), name=m["name"],
                                           epsilon=db["eps_inf"])
            for k, (delta, f_relax) in enumerate(zip(db["delta"], db["f_relax_hz"], strict=True)):
                material.SetDispersiveMaterialProperty(k, eps_delta=delta, eps_relax=1 / (2 * math.pi * f_relax))
            csx.AddProperty(material)
        else:
            material = csx.AddMaterial(m["name"], epsilon=m["eps"], kappa=m["kappa"])
        for solid in m["solids"]:
            _prism(material, solid, m["priority"], sheet)

    pec, metal = spec["metal"], csx.AddMetal("metal")
    for solid in (*pec["copper"], *pec["lid"]["walls"]):
        _prism(metal, solid, METAL_PRIORITY, sheet)
    if (plate := pec["lid"]["plate"]) is not None:
        metal.AddPolygon([plate["x"], plate["y"]], "z", plate["z"], priority=METAL_PRIORITY)
    for rod in pec["cylinders"]:
        (x, y), (z0, z1) = rod["at"], rod["z"]
        metal.AddCylinder([x, y, z0], [x, y, z1], rod["r"], priority=METAL_PRIORITY)
    for rod in pec["curves"]:
        (x, y), (z0, z1) = rod["at"], rod["z"]
        metal.AddCurve([[x, x], [y, y], [z0, z1]])

    for k, port in enumerate(spec["ports"], 1):
        on, r = 1 if k == excite else 0, port.get("R", 50)
        if port["kind"] == "curve":
            fdtd.AddCurvePort(k, r, port["start"], port["stop"], excite=on)
        else:
            fdtd.AddLumpedPort(k, r, port["start"], port["stop"], port["dir"], excite=on)
    for probe in spec.get("probes", ()):
        normal = {"norm_dir": probe["norm_dir"]} if "norm_dir" in probe else {}
        box = csx.AddProbe(probe["name"], p_type=probe["type"], weight=probe["weight"], **normal)
        box.AddBox(probe["start"], probe["stop"])
    for i, part in enumerate(spec["grid"]):
        value = {key: part[key] for key in ("R", "C", "L") if part.get(key) is not None}
        element = csx.AddLumpedElement(f"lumped_{i}", ny="xyz".index(part["dir"]), caps=True, **value)
        element.AddBox(part["start"], part["stop"])
    box = None
    if (nf := spec.get("nf2ff")) is not None:
        f_hz, f1, f2 = nf["f_hz"], pulse["f1"], pulse["f2"]
        cap = EMISSION_NF2FF_MAX if pulse.get("emission") else NF2FF_MAX
        # ponytail: a crash (E_WORKER_FAILED); an antenna's frequencies come from project.json's far_field.f_hz, which
        # check_project refuses outside the pulse band first
        if not (0 < len(f_hz) <= cap and all(f1 <= f <= f2 for f in f_hz)):
            raise ValueError(f"far-field frequencies {f_hz}: 1 to {cap}, each from f1 {f1:g} to f2 {f2:g} Hz")
        # accumulated every Nyquist/4 steps, the port probes' rate: at openEMS's default Nyquist rate a frequency
        # aliases at 2·f2 − f, worse toward f2 (design 5.5)
        box = fdtd.CreateNF2FFBox("nf2ff", frequency=f_hz, over_sampling=4,
                                  **({"start": nf["box"][0], "stop": nf["box"][1]} if "box" in nf else {}))
    if (near := spec.get("near_field")) is not None:
        # over-sampled 4 times as the far-field box is: at openEMS's default Nyquist rate a frequency aliases at
        # 2·f2 − f, worst at f2, which the top harmonic often is
        dump = csx.AddDump("near_field", dump_type=11, file_type=1, frequency=near["f_hz"], over_sampling=4)
        dump.AddBox(near["start"], near["stop"])
    return csx, fdtd, box
