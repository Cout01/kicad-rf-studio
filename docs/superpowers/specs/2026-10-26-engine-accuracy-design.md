# Engine accuracy after P0-B: Stage 1 plans 6 and 7 (design)

- **Status:** controller design, written on 2026-10-26 while the owner is unavailable. Every decision below is a
  **controller recommendation, owner unavailable**. The owner may override any of them.
- **Authority:** the Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, stays the only
  engine authority. This document plans changes to it. Each change lands as a numbered spec amendment (A-8 onward), in its
  own commit, only after the pre-registered rule that justifies it has passed.
- **Evidence:** `docs/validation/2026-10-25-stage1-exit.md`, `2026-10-25-p0-b.md` and `2026-10-24-p0-a.md`, plus the
  research of 2026-10-26 in `.superpowers/sdd/stage2-plan1-research/` (r1 mesh, r2 verify's L, r3 the miss above 2.1 GHz,
  r4 the rerun, r5 the spec frame; git-ignored, local).

## 1. Intent and why

P0-B was decided **fail at the ceiling** on 2026-10-25. Criterion 1 (verify against the co-simulation, spec §9.3) missed:
|ΔS21| at f0 was 0.1019 dB against 0.1 dB, and max |ΔS| up to f2 was 0.0926 against 0.03, at S11, 2.9705 GHz. So the
§7.6 what-if label stays on, `RETUNE_VALIDATED` stays False, and P0-C is recorded "do not start". The owner's original
order was "validate first, then the GUI". This work gives P0-B one fair second run on corrected engine code. If it passes,
P0-C becomes ready for the owner, and `RETUNE_VALIDATED` can flip once P0-C passes on the owner's board.

The research of 2026-10-26 split the miss into three causes, all measured offline on P0-B's stored records:

1. **Truncation at a structural mode (most of the band miss).** A real mode near 2.962 GHz (Q about 90; it is in both
   models, so it is not an artefact of verify) is still ringing when the co-simulation's jobs stop at 12–23 ns. The stop
   rule's monitor watches each job's own S column, with Normal's tolerance 2e-3 over a 1 ns lag. Closing the part ports
   magnifies what is left of the tail about six times: cutting every job 2 ns earlier moves the six-port by at most 0.0037
   but moves the closed result by 0.0191. Extrapolating each record's decaying tail (a matrix-pencil fit of the last 6 ns)
   brought max |ΔS| from 0.0926 to 0.0316 on the stored records. On verify's long P1 record, tails fitted from cuts at
   13.21, 16 and 20 ns reproduced the 30 ns S11 to within 0.0008.
2. **verify's L1 strips (most of the f0 miss; ruling OQ1).** verify builds an inductor as one cell joined to its pads by
   one-cell-wide PEC strips. Those strips add about 0.10–0.15 nH (closed form 0.126 nH over the box length). Removing that
   term moves ΔS21(f0) by about +0.059 dB, which leaves about −0.04 dB. It changes nothing above 2 GHz.
3. **A C1-branch term (the rest of the band miss).** After tails, S11's phase in verify still leads the co-simulation's by
   about +1.5° over 2.1–2.9 GHz. That fits a series inductance about 0.06 nH smaller in C1's branch in verify. The probable
   cause is A-7's full-width fill against the co-simulation's port box. It is a fit, not a measurement, and it is still
   unattributed.

Separately, D-31 put the **mesh-rule calibration** first. The rule's bias stops a masked GCPW at mesh n 2: E_FIT2D reads
+3.77 % against the 3 % gate. Every model's hash moves when the rule moves, so the rule must be settled before anything is
revalidated. Otherwise the rerun would go stale.

## 2. Goals

- **G1. Mesh rule (plan 6).** A GCPW slot edge gets a calibrated inside line. Every fixture section then passes the 3 %
  fit2d gate at n 2, and at n 3 too, except the lpf915 family. This must come with no regression under the acceptance in
  §5.1.
- **G2. Truncation (plan 7).** Every S the tool reports (run, retune, verify) is free of the truncation error the stop rule
  leaves near a slowly decaying mode.
- **G3. verify's construction (plan 7).** verify's own S represents the ideal part values. The L strip term is
  compensated, and the C1-branch term is either attributed and compensated by an estimate, or registered as a known
  difference with its range.
- **G4. One pre-registered P0-B rerun (P0-B2, plan 7)** on the final code, judged by §9.3's unchanged criteria.
- **G5. References.** P0-A's rows and decisions, P0-D's nine references and the eight trace fixtures are regenerated on
  the new code, and main stays green after each plan.

## 3. Non-goals and anti-goals

**Non-goals.**
- No GUI work. The Stage 2 spec owns the PySide6 client, the button, live import, the advanced panel, the what-if UI,
  E12/E24 snapping and packaging.
- No limit moves (D-22): the fit2d 3 % gate, the criterion-1 limits, the stop presets, K_MAX 0.45, T_MAX_S 40 ns, the dt
  floor and the growth threshold all stay.
- No narrowing of E_STAIRCASED, no preview of a refused port box, and no new user-facing `project.json` field. These are
  Stage 2 questions (O-24).
- No step-edge role with lint relief (the lpf915 family at n 3). It stays a stated limit, and E_FIT2D_FINE's limit raise
  stays the remedy.
- No P0-C run. That is the owner's step.

**Anti-goals.** Any of these would make the work a failure even if it ran:
- a calibration that trades rows between families (R-P2-26);
- a gate that passes because a limit, a tolerance or a pre-registered expectation moved after the data was seen;
- a tail model that invents a resonance, hides a diverging or growing job, or changes a verdict of the stop rule.

## 4. Constraints

- **Execution model:** D-5..D-10 carry over. Code tasks are test-first. Gate runs happen on an otherwise idle PC: no
  pytest, openEMS or EMerge alongside, and nothing committed to `src/` or `tools/` during a run. Step records are
  resumable, keyed by model hash and code id. The gates drive the product as subprocesses. Any dB-judged comparison runs at
  Normal.
- **A fresh P0 folder for this round:** `%LOCALAPPDATA%\kicad-rf-studio-p0-2`, passed explicitly with `--p0`/`--out`.
  Stage 1's `kicad-rf-studio-p0` stays frozen, because it is the evidence behind the committed reports.
- **Plan 5's Global Constraints** carry over whole: SPDX headers; CATALOG-only product strings; no new runtime
  dependency; the import boundaries; units and frames; the report rules (D-51, D-52); privacy; the controller-recommendation
  marking; graphify; no co-author line; never `--no-verify`; nothing pushed.
- **Pre-registration:** each expected result and each decision rule is written into the plan and the ledger, and
  committed, before the measurement that judges it. This is OQ1's practice.
- **Timebox:** D-4's window still counts: target 2026-11-05 to 2026-11-12, ceiling 2026-11-19. At the ceiling all P0 work
  stops, and the exit report gets an addendum with the data.

## 5. Decisions

### 5.1 Plan 6: the mesh-rule calibration

- **The objective is fit2d.** P0-A measured fit2d against FDTD at max |δ| 0.5293 pp, so a 2D solve stands in for FDTD
  during the search. No FDTD runs during the search.
- **The harness.** Plan 2's ratchet harness (in its archive zip; ported to HEAD during research as `hrun.py`; it
  reproduces plan 2's rows exactly) becomes a committed dev tool under `tools/`, with a frozen baseline taken on HEAD at
  reach 6. If plan 2's 1061 synthetic boards can be regenerated deterministically from a committed generator, they are
  generated into a scratch folder at run time and never committed. If they cannot, the harness stays outside the repo, and
  only its baseline and results go into the report. The axes harness (246,064 synthetic axes) is generated either way.
- **The new role.** A slot edge is an edge that faces the other side's metal across a gap of at most FACE = 4d. It gets
  its own inside depth, IN_slot. Everything else stays as built: the open, step, cut and forced edges, OUT, dz0 and the
  edge cell.
- **Search space, fixed before any search:**
  - IN_slot ∈ {d/8 + GRID_TOL, 9d/64, 5d/32, d/6, 3d/16, 5d/24};
  - an h/d gate ∈ {none, 2, 3, 4.2};
  - applied to lone slot cells only, or to every served slot cell.

  That is 48 candidates, about 5 minutes each.
- **Acceptance, in order, fixed before any search:**
  1. Every fixture section reads |fit2d| < 3 % at n 2, and at n 3 too, except lpf915 and lpf915-45.
  2. Zero axis regressions (lint, ratio, d/3, error) against HEAD's baseline, with h unset, 2d and 5d.
  3. At most 5 of the 2142 board rows pass on HEAD and fail with the candidate. Each one is named, none is a fixture, and
     no family's pass count falls below HEAD's.
  4. The GCPW coupons' fit2d lies between −1.5 % and +1.5 % at n 2 and n 3, and microstrip fit2d is unchanged.
  5. Among the candidates that pass, the largest pass count wins, then the smallest max |fit2d| over the GCPW families.
- **Round cap.** There is one search over that grid. If no candidate passes, the rule does not change, and plan 6 ends with
  its report and the stated limits as they are. No second round.
- **Order after the search passes** (controller call, from the builder check):
  1. The rule's code, its tests and the re-pinned values land test-first.
  2. In the fresh P0 folder, P0-A runs in full (17 steps, about 3.1 h). D-25..D-30 are applied to its data exactly as plan
     5 pre-registered them; no rule is rewritten after the data.
  3. Only if P0-A's verdict is pass:
     - amendment A-8 goes into §5.4 (inside lines by edge role). The same amendment brings the stale reach text up to date
       (§5.4 L282 and §12 L673 still say 3 h; REACH_H has been 6 since D-37);
     - P0-B's B1 runs alone at reach 3 (about 3.2 h; the old harness pinned to `p0a.PIN`), as the source of P0-D's lpf915
       reference;
     - P0-D's nine references and the eight trace fixtures are regenerated from the fresh folder, with Tasks 19 and 20's
       commands.
  4. The calibration report and the P0-A re-check report are written; then decide and merge.

  If a model hash does not move, its old record stands and is not rerun (OQ4's hash check).
- **If the re-check moves a decided branch** (controller call). That branch is applied as written, because the rule is
  the gate's, not this design's. The likely case is D-27: the slot role moves the axis-aligned twin's Z0 more than the
  staircased one, so the 45° twin's |dz0| may fall under 5 %. Then D-27's keep branch applies. E_STAIRCASED returns to a
  warning that names the new measured error, and the "7.0 %" text goes. If D-27 still refuses, the message's figure
  becomes the new measured value. D-29's and D-30's branches are applied the same way.
- **If P0-A's verdict fails under the new rule** (any D-25 row out of its limit): the rule's code is reverted in one
  commit, and A-8, B1 and the regeneration do not happen. The re-check is not repeated, and the report states that FDTD
  rejected the calibration. The stated limits stay as they are.

### 5.2 Plan 7: consistency, then P0-B2

Plan 7 starts with its own short research phase on plan 6's merged code. These decisions frame it.

- **Tails (G2).**
  - The S of every record is its DFT cut at the stop rule's verdict, plus its fitted decaying tail.
  - The fit is a matrix pencil over the last 6 ns of each channel, keeping decaying poles only. The model order is
    bounded and the fit's residual is checked. When the fit fails its own check, S falls back to the plain DFT and a W_
    code says so.
  - It applies wherever records become S: `waves.s_matrix` and the tools' `p0.s_of`.
  - The stop rule's verdicts and cut times do not change, so the committed trace replays stay valid.
  - A run prints one warning when the tail contributes more than 0.02 to any closed-chain |S| up to f2, naming where.
  - **Pre-registered checks:** on verify's long P1 record, tails from cuts at 13.21, 16 and 20 ns reproduce the 30 ns S to
    within 0.002 at every frequency up to f2. Offline, on P0-B's stored records, the tail-corrected comparison reads
    max |ΔS| ≤ 0.035.
  - Amendment A-9 records this.
- **The L strips (G3).**
  - verify's grid L becomes L − ΔL. ΔL is the closed-form partial inductance of the strips over the box length (0.126 nH
    on lpf915; the formula's error is about ±30 %).
  - verify refuses when L − ΔL ≤ 0. The K check uses the compensated L. The K_MAX sweep's harness keeps uncompensated
    values.
  - The one-cell construction itself stays, so the K_MAX evidence holds.
  - **Pre-registered:** ΔS21(f0) shifts by +0.059 ± 0.005 dB against the uncompensated construction on the same mesh.
  - Amendment A-10 goes into §7.6 (L470).
- **The box term behind the C1-branch residual (G3; controller call, from the builder check).**
  - **What it is.** A grid C (LEtype=0) cannot carry a series L, and §7.6 bars LEtype=1. So the term cannot be
    compensated inside verify the way the L strips are.
  - **One estimator for every part box.** Plan 7's research picks a single CPU-only estimator: a closed form or PEEC of the
    construction difference between the co-simulation's port box and the in-grid construction. It applies to every part
    port, of every kind, with the same formula. It is never a per-part fit, and never C1 alone because a fit pointed there.
  - **Where it goes, if adopted.** In the co-simulation's closure, beside C_box, as a series L_box term per part port. The
    closure is shared by run, retune and verify's comparison, so users' results move with it and the gate judges what users
    see. Amendment A-11 records it.
    - Rejected: compensating only in P0-B2's harness comparison (the anti-goal of a moved expectation).
    - Rejected: narrowing verify's fill (A-7's ringing risk).
  - **Adoption rule, fixed before it is computed.** Offline, on P0-B's stored records with tails, the estimator must bring
    max |ΔS| up to f2 to 0.025 or less without worsening ΔS21(f0). Otherwise it is not adopted, and the term is registered
    as a known difference with the estimate's range before P0-B2.
- **How the fixes are checked, and what a miss does (controller call, from the builder check).**
  - **A-10's check.** It runs on a single-L coupon (a GCPW line with an 0402 pad gap): one co-simulation and two verify
    runs, uncompensated and compensated, as scratch FDTD before the gate (about 10 minutes each).
    - Pre-registered: the uncompensated pair's fitted ΔL lies inside the closed form's ±30 % band, and the compensated
      pair's |ΔS21(f0)| is 0.02 dB or less.
    - It is not measured on P0-B2's project, so no extra multi-hour verify run is needed.
  - **Expected values.** They are recomputed on plan 6's mesh during plan 7's research, before any measurement they
    judge.
  - **A-9's tail method.** Its parameters (the 6 ns window, the order bound, the fit check) are frozen in plan 7's plan
    before it is built. Its checks run once, with no tuning against the stored records afterwards, on data not used to
    develop it as well: plan 6's new B1 record and the committed traces. Verify's long P1 record and P0-B's stored
    comparison are the development data.
  - **A miss.** A fix that misses its own check is not adopted as is. A redesign needs a new pre-registration and new data.
  - **When P0-B2 runs.** Only when every adopted fix has passed its check, and an offline recompute of P0-B's stored records
    with the adopted corrections predicts criterion 1 within §9.3's limits. Otherwise plan 7 ends with its fixes merged,
    P0-B2 is not spent, and the report says why.
- **P0-B2 (G4).**
  - **Configuration:** a new small gate in the fresh folder, with steps `p0b2-B1` (lpf915 with `new`'s defaults, reach 6,
    `t_max_s` 80 ns set in its project) and `p0b2-B2` (verify of that project).
  - **Blocking:** criterion 1 with §9.3's unchanged limits, and every B1 and B2 job converged with D-40's evidence.
  - **Dropped:** B4, because the TX side is excluded and E_STAIRCASED refuses lpf915-45.
  - **Not blocking:** EMerge. It stays the owner's option.
  - **Before the run:** every fixed item registers its expected known difference, and the whole pre-registration is
    committed.
  - **Ceiling:** one run. A code change after the result spends it. An interrupted or loaded step resumes and does not
    count.
  - **On pass:** the controller recommends withdrawing P0-C's "do not start". `RETUNE_VALIDATED` still waits for P0-C.
  - **On fail:** the label stays and the miss is reported against the pre-registered terms.
- **After P0-B2:**
  - regenerate P0-D's references, since tails change the replayed S;
  - write the P0-B2 report and an addendum to the exit report;
  - decide and merge.

## 6. Left to the builder

Within the decisions above, the builder chooses:
- module and function names, file layout, and test names and shapes;
- the matrix pencil's numerical details, within the stated safeguards;
- the harness's command line;
- how plans 6 and 7 are cut into tasks;
- the report wording, within D-51.

Where the builder finds a decision here that the code contradicts, the Stage 1 spec and the code's tests win, and the
controller rules on it in the plan's ledger.

## 7. Owner items this work leaves open

- P0-C on the private board (or confirming "do not start"), and flipping `RETUNE_VALIDATED` after it.
- The lpf915 family at n 3 (a step-edge role with lint relief).
- Narrowing E_STAIRCASED to 45° segments: P0-A measured the arc twin's Z0 within budget.
- The items already in the exit report: the time policy, the identity rewrite and c20f71b, the deny-list review,
  RFsim/NOTICE, the GUI click, the first push, PyPI and EMerge.
