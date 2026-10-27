# Plan 6's mesh-rule calibration (2026-10-27)

## 1. Verdict

**Winner: `1-6_none_served`; the rule changes.** Of the 48 pre-registered candidates, 18 meet acceptance conditions 1–4, and condition 5 chose `1-6_none_served`. A slot edge's inside line now sits d/6 deep (`SLOT_IN` = 1/6), with no substrate gate (`SLOT_GATE` = 0), in its own cell and in every served cell whose deepest edge it is (`SLOT_SERVED` = True). The winner passes 2044 of the 2142 board rows, against the rule as built's 1966. It fails 4 rows that the rule as built passes, all by fit2d, leaves no family below the baseline, breaks no axis, and puts the GCPW coupons at −0.113 … +1.049 % in fit2d. **No candidate was struck:** the winner passed every gate-asserting product test (Task 6, `0813f84`). **P0-A's FDTD re-check passed** on 2026-10-26 (`2026-10-26-p0-a.md`), so the rule stays, and **amendment A-8 landed** (`144161a`). B1 ended six converged, with a dt ratio of 1.1056 against D-30's 0.85. **lpf915's reference was regenerated** from B1's record, with the other eight references and the eight traces (Task 10's full branch, `67518c4`). The README's cost excerpt stands, since its Cells line did not move. Each decision is a controller recommendation, owner unavailable (section 4).

## 2. Inputs

- **JSON:** `2026-10-27-mesh-calibration.json` beside this report is the search's `meshcal.json`, as `tools/meshcal.py` wrote it in `<P0-2>/meshcal/`. Its table, `meshcal.md`, is copied in section 3.
- **Run:** Task 5, one command, `.venv\Scripts\python.exe tools\meshcal.py --harness <R1> --boards <P0-2>\meshcal\boards --out <P0-2>\meshcal`, from 06:48 to 12:05 on 2026-10-26. It exited 0 after 50 steps: the baseline, the shakedown and the 48 candidates. No step was loaded.
- **Commit and code (`versions`):** commit `2449427`, code `6599bdf5fc7dbfe0bc0c081e9ff04731c50384a4`. Python 3.14.2, openEMS 0.37.0, CSXCAD 0.7.0, Windows-11-10.0.26200-SP0, 16 CPUs. The slot role is `a5bee9c`, the guard `4b38b36`, and the search with its acceptance `add81a5`.
- **r1's harness, outside the repo:** `<R1>` is `.superpowers\sdd\stage2-plan1-research\r1-mesh\scripts` (git-ignored). `meshcal.PINNED` pins its 11 files by sha256: `hrun.py` and `all_r6.jsonl`, and in `ax/` `launch.py`, `axrun.py`, `common.py`, `axes.py`, `axes2.py`, `caxes.py`, `a_head.json`, `a_head_h2.json` and `a_head_h5.json`. `run` checked them before any step. Each evaluation rebuilds `<P0-2>/meshcal/tree` from the repo's `src`, with one line appended to `rule.py` that sets the candidate's three constants, so r1's scripts run unchanged.
- **Boards:** plan 2's 1061 synthetic boards plus the 10 fixtures, at n 2 and 3: 2142 rows, at reach 6, each board at its own top of band (3 GHz, but for 14 ms_step boards at 10 and 20 GHz). The boards stay in `<P0-2>/meshcal/boards`.
- **Axes:** 246,064 synthetic axes, each run at h unset, 2d and 5d.
- **The grid:** 48 candidates, 6 depths × 4 gates × 2 scopes, named depth_gate_scope. The depth `SLOT_IN` is d/8, 9d/64, 5d/32, d/6, 3d/16 or 5d/24, and the inside line sits max(SLOT_IN·d, d/8 + GRID_TOL) deep. The gate `SLOT_GATE` is none, 2, 3 or 4.2: the slot depth holds where the substrate h is at least that many d (an unset h passes every gate). The scope is lone (a cell of the slot edge's own) or served (also any served cell whose deepest edge is a slot edge). A slot edge faces metal across a gap of at most 4d. Its outside line stays 3d/4 out, and every other edge keeps the rule as built.
- **The guard** (Task 2): the slot depth holds on an axis only where its lines pass the edge lint and the d/3 merge. Elsewhere, and after a RuntimeError in the slot pass, the axis keeps the as-built lines.
- **The baseline check and the shakedown:** the baseline (the role off) had to reproduce r1's frozen `all_r6.jsonl` line by line and its three `a_head*.json` files as parsed dicts. Then, before any candidate, the three axes runs of `1-6_none_served` (r1's ungated served d/6, which broke 3168 axes before the guard) had to show 0 axis regressions against the baseline.

## 3. Measured value against limit

**The conditions** (pre-registered in `tools/meshcal.py`, `add81a5`). A row passes when it is built, has lint 0, ratio 0, no cell under d/3 and every |fit2d| under 3 %. A missing row or axis, an error, a ValueError's text or a NaN counts as failed.

- c1: every fixture row passes at n 2 and 3, lpf915 and lpf915-45 at n 2 only.
- c2: no axis that the baseline keeps clean fails, at h unset, 2d or 5d.
- c3: at most 5 rows that the baseline passes fail, none of them a fixture, and no family passes fewer rows than in the baseline.
- c4: coupon_ms's and coupon_ms_masked's fit2d is unchanged, and every section of coupon_gcpw, coupon_gcpw_masked, coupon_gcpw_pads, coupon_dense and coupon_gcpw_arc reads −1.5 to +1.5 % inclusive, at n 2 and 3.
- Condition 5: of the candidates that meet c1–c4, the most passes, then the smallest `gcpw_max` (the largest |fit2d| over c4's GCPW sections), then the grid's order.

**Baseline and shakedown.** The role off passes 1966 of 2142 rows, and 24,745, 24,744 and 24,745 axes fail at h unset, 2d and 5d. These equal r1's frozen files. The shakedown showed 0, 0 and 0 axis regressions, so the search went on. The baseline itself fails c1 and c4: coupon_gcpw_masked reads 3.768 % at n 2, and the GCPW coupons read +1.868 … +3.768 %.

**The candidates** (`meshcal.md`'s table, as rendered):

| id | c1 | c2 | c3 | c4 | pass | passes | regressions | families_below | gcpw_coupons | gcpw_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-8_none_lone | True | True | False | True | False | 2016 | ['a:ms_cpw_pads/ms_g0.71_pNone n=2', 'a:ms_cpw_pads/ms_g0.71_p0.01 n=2', 'a:ms_cpw_pads/ms_g0.9_pNone n=2', 'a:ms_cpw_pads/ms_g0.9_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_pNone n=2', 'a:ms_cpw_pads/ms_g1.1_p0.01 n=2', 'a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/m_g0.6_pNone n=2', 'a:gcpw_gap_pads/m_g0.8_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:ms_pour/ms_g0.7_none n=2', 'b:ms_pour/ms_g0.9_none n=2', 'b:ms_pour/ms_g1.1_none n=2', 'b:ms_pour/ms_g1.4_none n=2', 'b:gcpw_gap/g0.4 n=2', 'b:gcpw_gap/g0.5 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:gcpw_gap_pads', 'a:ms_cpw_pads', 'b:gcpw_gap', 'b:ms_pour'] | [-1.215, -0.035] | 1.215 |
| 1-8_none_served | True | True | False | True | False | 2005 | ['a:ms_cpw_pads/ms_g0.71_pNone n=2', 'a:ms_cpw_pads/ms_g0.71_p0.01 n=2', 'a:ms_cpw_pads/ms_g0.71_p0.02 n=2', 'a:ms_cpw_pads/ms_g0.9_pNone n=2', 'a:ms_cpw_pads/ms_g0.9_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_pNone n=2', 'a:ms_cpw_pads/ms_g1.1_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_p0.02 n=2', 'a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.05 n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.05 n=2', 'a:gcpw_gap_pads/m_g0.6_pNone n=2', 'a:gcpw_gap_pads/m_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/m_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/m_g0.8_pNone n=2', 'a:gcpw_gap_pads/m_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/m_g0.8_p0.03 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'a:eps/ms_g0.7105_p0.02 n=2', 'a:eps/ms_g1.1005_p0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:eps/g_g0.6005_p0.03 n=2', 'a:eps/g_g0.6005_p0.05 n=2', 'a:eps/gm_g0.6005_p0.015 n=2', 'a:eps/gm_g0.6005_p0.03 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:ms_pour/ms_g0.7_none n=2', 'b:ms_pour/ms_g0.7_w0.02 n=2', 'b:ms_pour/ms_g0.9_none n=2', 'b:ms_pour/ms_g1.1_none n=2', 'b:ms_pour/ms_g1.1_w0.02 n=2', 'b:ms_pour/ms_g1.4_none n=2', 'b:gcpw_gap/g0.4 n=2', 'b:gcpw_gap/g0.5 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:eps', 'a:gcpw_gap_pads', 'a:ms_cpw_pads', 'b:gcpw_gap', 'b:ms_pour'] | [-1.215, -0.035] | 1.215 |
| 1-8_2_lone | True | True | False | True | False | 2016 | ['a:ms_cpw_pads/ms_g0.71_pNone n=2', 'a:ms_cpw_pads/ms_g0.71_p0.01 n=2', 'a:ms_cpw_pads/ms_g0.9_pNone n=2', 'a:ms_cpw_pads/ms_g0.9_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_pNone n=2', 'a:ms_cpw_pads/ms_g1.1_p0.01 n=2', 'a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/m_g0.6_pNone n=2', 'a:gcpw_gap_pads/m_g0.8_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:ms_pour/ms_g0.7_none n=2', 'b:ms_pour/ms_g0.9_none n=2', 'b:ms_pour/ms_g1.1_none n=2', 'b:ms_pour/ms_g1.4_none n=2', 'b:gcpw_gap/g0.4 n=2', 'b:gcpw_gap/g0.5 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:gcpw_gap_pads', 'a:ms_cpw_pads', 'b:gcpw_gap', 'b:ms_pour'] | [-1.215, -0.035] | 1.215 |
| 1-8_2_served | True | True | False | True | False | 2005 | ['a:ms_cpw_pads/ms_g0.71_pNone n=2', 'a:ms_cpw_pads/ms_g0.71_p0.01 n=2', 'a:ms_cpw_pads/ms_g0.71_p0.02 n=2', 'a:ms_cpw_pads/ms_g0.9_pNone n=2', 'a:ms_cpw_pads/ms_g0.9_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_pNone n=2', 'a:ms_cpw_pads/ms_g1.1_p0.01 n=2', 'a:ms_cpw_pads/ms_g1.1_p0.02 n=2', 'a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.05 n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.05 n=2', 'a:gcpw_gap_pads/m_g0.6_pNone n=2', 'a:gcpw_gap_pads/m_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/m_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/m_g0.8_pNone n=2', 'a:gcpw_gap_pads/m_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/m_g0.8_p0.03 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'a:eps/ms_g0.7105_p0.02 n=2', 'a:eps/ms_g1.1005_p0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:eps/g_g0.6005_p0.03 n=2', 'a:eps/g_g0.6005_p0.05 n=2', 'a:eps/gm_g0.6005_p0.015 n=2', 'a:eps/gm_g0.6005_p0.03 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:ms_pour/ms_g0.7_none n=2', 'b:ms_pour/ms_g0.7_w0.02 n=2', 'b:ms_pour/ms_g0.9_none n=2', 'b:ms_pour/ms_g1.1_none n=2', 'b:ms_pour/ms_g1.1_w0.02 n=2', 'b:ms_pour/ms_g1.4_none n=2', 'b:gcpw_gap/g0.4 n=2', 'b:gcpw_gap/g0.5 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:eps', 'a:gcpw_gap_pads', 'a:ms_cpw_pads', 'b:gcpw_gap', 'b:ms_pour'] | [-1.215, -0.035] | 1.215 |
| 1-8_3_lone | True | True | False | True | False | 2020 | ['a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'b:gcpw_gap/g0.4 n=2'] | ['b:gcpw_gap'] | [-1.215, -0.035] | 1.215 |
| 1-8_3_served | True | True | False | True | False | 2022 | ['a:gcpw_gap_pads/u_g0.45_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3', 'b:gcpw_gap/g0.4 n=2'] | ['b:gcpw_gap'] | [-1.215, -0.035] | 1.215 |
| 1-8_4.2_lone | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3'] | [] | [-1.215, -0.035] | 1.215 |
| 1-8_4.2_served | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:ms_jog/gm_0.02 n=3'] | [] | [-1.215, -0.035] | 1.215 |
| 9-64_none_lone | True | True | False | True | False | 2031 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.742, 0.321] | 0.742 |
| 9-64_none_served | True | True | False | True | False | 2031 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.05 n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.05 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:eps/g_g0.6005_p0.03 n=2', 'a:eps/g_g0.6005_p0.05 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:eps', 'a:gcpw_gap_pads', 'b:gcpw_gap'] | [-0.742, 0.321] | 0.742 |
| 9-64_2_lone | True | True | False | True | False | 2031 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.742, 0.321] | 0.742 |
| 9-64_2_served | True | True | False | True | False | 2031 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.6_p0.05 n=2', 'a:gcpw_gap_pads/u_g0.8_pNone n=2', 'a:gcpw_gap_pads/u_g0.8_p0.015 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.03 n=2', 'a:gcpw_gap_pads/u_g0.8_p0.05 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:eps/g_g0.6005_p0.03 n=2', 'a:eps/g_g0.6005_p0.05 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g0.8 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['a:eps', 'a:gcpw_gap_pads', 'b:gcpw_gap'] | [-0.742, 0.321] | 0.742 |
| 9-64_3_lone | True | True | True | True | True | 2022 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.742, 0.321] | 0.742 |
| 9-64_3_served | True | True | True | True | True | 2024 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.742, 0.321] | 0.742 |
| 9-64_4.2_lone | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.742, 0.321] | 0.742 |
| 9-64_4.2_served | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.742, 0.321] | 0.742 |
| 5-32_none_lone | True | True | False | True | False | 2033 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.27, 0.707] | 0.707 |
| 5-32_none_served | True | True | False | True | False | 2040 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.27, 0.707] | 0.707 |
| 5-32_2_lone | True | True | False | True | False | 2033 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.27, 0.707] | 0.707 |
| 5-32_2_served | True | True | False | True | False | 2040 | ['a:gcpw_gap_pads/u_g0.6_pNone n=2', 'a:gcpw_gap_pads/u_g0.6_p0.015 n=2', 'a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2', 'a:eps/g_g0.6005_p0.015 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2', 'b:gcpw_gap/g0.6 n=2', 'b:gcpw_gap/g1.0 n=2'] | ['b:gcpw_gap'] | [-0.27, 0.707] | 0.707 |
| 5-32_3_lone | True | True | True | True | True | 2022 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.27, 0.707] | 0.707 |
| 5-32_3_served | True | True | True | True | True | 2024 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.27, 0.707] | 0.707 |
| 5-32_4.2_lone | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.27, 0.707] | 0.707 |
| 5-32_4.2_served | True | True | True | True | True | 2005 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/g_0.02 n=3', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.27, 0.707] | 0.707 |
| 1-6_none_lone | True | True | True | True | True | 2036 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [-0.115, 1.049] | 1.049 |
| 1-6_none_served | True | True | True | True | True | 2044 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [-0.113, 1.049] | 1.049 |
| 1-6_2_lone | True | True | True | True | True | 2036 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [-0.115, 1.049] | 1.049 |
| 1-6_2_served | True | True | True | True | True | 2044 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2', 'a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [-0.113, 1.049] | 1.049 |
| 1-6_3_lone | True | True | True | True | True | 2023 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.115, 1.049] | 1.049 |
| 1-6_3_served | True | True | True | True | True | 2025 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.113, 1.049] | 1.049 |
| 1-6_4.2_lone | True | True | True | True | True | 2006 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.115, 1.049] | 1.049 |
| 1-6_4.2_served | True | True | True | True | True | 2006 | ['a:ms_jog/g_0.02 n=2', 'a:ms_jog/gm_0.02 n=2'] | [] | [-0.113, 1.049] | 1.049 |
| 3-16_none_lone | True | True | True | False | False | 2037 | ['a:ms_jog/g_0.02 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [0.531, 1.728] | 1.728 |
| 3-16_none_served | True | True | True | False | False | 2045 | ['a:ms_jog/g_0.02 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [0.533, 1.728] | 1.728 |
| 3-16_2_lone | True | True | True | False | False | 2037 | ['a:ms_jog/g_0.02 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [0.531, 1.728] | 1.728 |
| 3-16_2_served | True | True | True | False | False | 2045 | ['a:ms_jog/g_0.02 n=2', 'a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2'] | [] | [0.533, 1.728] | 1.728 |
| 3-16_3_lone | True | True | True | False | False | 2023 | ['a:ms_jog/g_0.02 n=2'] | [] | [0.531, 1.728] | 1.728 |
| 3-16_3_served | True | True | True | False | False | 2025 | ['a:ms_jog/g_0.02 n=2'] | [] | [0.533, 1.728] | 1.728 |
| 3-16_4.2_lone | True | True | True | False | False | 2006 | ['a:ms_jog/g_0.02 n=2'] | [] | [0.531, 1.728] | 1.728 |
| 3-16_4.2_served | True | True | True | False | False | 2006 | ['a:ms_jog/g_0.02 n=2'] | [] | [0.533, 1.728] | 1.728 |
| 5-24_none_lone | True | True | True | False | False | 2025 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_none_served | True | True | True | False | False | 2031 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_2_lone | True | True | True | False | False | 2025 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_2_served | True | True | True | False | False | 2031 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_3_lone | True | True | True | False | False | 2015 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_3_served | True | True | True | False | False | 2017 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_4.2_lone | True | True | True | False | False | 2001 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |
| 5-24_4.2_served | True | True | True | False | False | 2001 | ['a:ms_jog/g_0.02 n=2'] | [] | [1.023, 2.408] | 2.408 |

- c1 and c2 hold for all 48. Every candidate brings coupon_gcpw_masked at n 2 under 3 %, none breaks an axis (`axes_regressions` is 0, 0 and 0 for each), and coupon_ms's and coupon_ms_masked's fit2d is unchanged under all 48.
- 14 fail c3: the d/8 candidates at gates none, 2 and 3 (6 to 47 regressions, 1 to 5 families below), and the 9d/64 and 5d/32 candidates at gates none and 2 (8 to 19 regressions, with b:gcpw_gap below in each).
- 16 fail c4: every 3d/16 candidate (GCPW coupons up to +1.728 %) and every 5d/24 one (up to +2.408 %), as predicted.
- 18 meet c1–c4: d/8 at gate 4.2, 9d/64 and 5d/32 at gates 3 and 4.2, and all eight d/6 candidates. Under condition 5, `1-6_none_served` and `1-6_2_served` lead with 2044 passes and tie at a `gcpw_max` of 1.049 %, so the grid's order picks `1-6_none_served`.
- The plan's prediction held: a no-gate candidate at or near d/6, such as `1-6_none_served`, with about 2042 passes or more, 4 fit2d regressions and no family below the baseline.

**The winner against the rule as built** (`rows/off.jsonl` against `rows/1-6_none_served.jsonl`). 82 rows newly pass and 4 regress, a net gain of 78. The 4 regressions are all by fit2d; their lint, ratio and d/3 stay 0.

| row | off fit2d (%) | winner fit2d (%) |
| --- | --- | --- |
| a:ms_jog/g_0.02 n=2 | -0.876, -2.753 | -2.014, -3.87 |
| a:ms_jog/gm_0.02 n=2 | -0.087, -2.084 | -1.322, -3.294 |
| a:thin_eps/m_h0.1_w0.2_g0.15_p-0.025 n=2 | 0.974 | 3.106 |
| a:thin_eps/m_h0.1_w0.18_g0.12_p-0.025 n=2 | 1.505 | 3.753 |

Passing rows by family, off → winner: gp_sq 68 → 90 of 90, a:thin_eps 98 → 121 of 160, a:thin_gcpw 75 → 88 of 96, a:ms_jog 63 → 69 of 72, b:gcpw_step 12 → 16 of 18, a:gcpw_gap_pads 111 → 114 of 120, a:eps 94 → 96 of 96, fixtures 17 → 18 of 20, and one row more in each of a:ms_cpw_pads, b:gcpw_gap_pads, b:ms_pour and gp_i. Every other family is unchanged.

The fixtures' fit2d (%, one value per section; lpf915's sections are RF_A at 0.25 mm, RF_A at 0.6 mm, RF_B, RF_C and RF_OUT):

| fixture | n | off | winner |
| --- | --- | --- | --- |
| coupon_ms | 2 | -0.095 | -0.095 |
| coupon_ms | 3 | 0.257 | 0.257 |
| coupon_ms_masked | 2 | 0.415 | 0.415 |
| coupon_ms_masked | 3 | 0.656 | 0.656 |
| coupon_gcpw | 2 | 2.534 | 0.043 |
| coupon_gcpw | 3 | 1.895 | 0.193 |
| coupon_gcpw_masked | 2 | 3.768 | 1.049 |
| coupon_gcpw_masked | 3 | 2.786 | 0.912 |
| coupon_gcpw_pads | 2 | 2.469 | -0.113 |
| coupon_gcpw_pads | 3 | 1.998 | 0.272 |
| coupon_dense | 2 | 2.54 | 0.042 |
| coupon_dense | 3 | 1.896 | 0.191 |
| coupon_gcpw_arc | 2 | 2.518, 2.503 | 0.042, 0.039 |
| coupon_gcpw_arc | 3 | 1.881, 1.868 | 0.19, 0.185 |
| coupon_gcpw_45 | 2, 3 | no section | no section |
| lpf915 | 2 | 2.521, 1.448, 2.323, 1.918, 1.918 | 1.304, 1.454, 2.329, 1.924, 1.924 |
| lpf915 | 3 | 4.195, 3.43, 4.322, 3.91, 3.91 | 2.54, 3.433, 4.325, 3.913, 3.913 |
| lpf915-45 | 2 | 2.369, 1.514, 2.763, 1.946, 1.985 | 1.181, 1.523, 2.772, 1.955, 1.994 |
| lpf915-45 | 3 | 4.058, 3.574, 4.848, 4.015, 4.054 | 2.443, 3.576, 4.85, 4.017, 4.056 |

Every fixture row keeps lint, ratio and d/3 at 0. Only lpf915 at n 3 and lpf915-45 change their line counts, by 1 to 4 lines in x or y.

**P0-A** (2026-10-26, `2026-10-26-p0-a.md`): verdict pass, no fails. D-25: every axis-aligned row meets |dz0| ≤ 5 % and |deeff| ≤ 3 %; the smallest margin is coupon_gcpw_arc at n 2, s0, at +2.707 % in εeff. D-26: both mask-shift pairs pass. D-27: the largest |dz0| is 4.637 % against the 5 % budget, and both twins read less at n 3. D-28: the pad coupon passes. D-29: the largest |δ| is 0.5293 pp against 1 pp. D-30: the smallest dt ratio is 0.904 against 0.85, and the stray-cell variant (0.5716) trips E_DT_FLOOR. The largest e_fit is 1.053 %, from coupon_gcpw_masked at n 2 (Stage 1: 3.781 %).

**B1** (Task 9): `tools/p0b/harness.py --out <P0-2> --only B1` at `ea0ac09`, lpf915 at reach 3 (`p0a.PIN`) with its 3 % fit2d gate pinned. OQ4's hash check printed True first: lpf915's reach-3 model `1ce63ec89d3f` against the reference's `20f6c687ef49`. B1 exited 0 with its six runs converged. **Its dt ratio is 1.1056 against D-30's 0.85: pass.** The smallest dt ratio over plan 6's rule-made P0 meshes is therefore P0-A's 0.904, on the pad coupon.

**P0-D's references** (Task 10, full branch, `67518c4`): all nine references and the eight traces were regenerated from `<P0-2>`. Each reference's spec_hash prefix and t_cut (s), old → new:

| reference | spec_hash | t_cut |
| --- | --- | --- |
| coupon_ms | 28616775, unchanged | 4.0906113e-09, unchanged |
| coupon_ms_masked | 2c012727, unchanged | 4.09310285e-09, unchanged |
| coupon_gcpw | 59a16fe2 → 6c6204dd | 4.09378886e-09 → 4.09286853e-09 |
| coupon_gcpw_masked | fe9668a8 → 89edbb9f | 4.09378886e-09 → 4.09286853e-09 |
| coupon_dense | 1494a5a3 → fa6ee967 | 4.09378886e-09 → 4.09286853e-09 |
| coupon_gcpw_45 | 447b11b5, unchanged | 4.09371093e-09, unchanged |
| coupon_gcpw_arc | 2d13bf2b → e1dd992a | 4.09756158e-09 → 4.09776169e-09 |
| coupon_gcpw_pads | 65344607 → 896ac880 | [4.0546545e-09 ×2] → [4.05432229e-09 ×2] |
| lpf915 | 20f6c687 → 1ce63ec8 | [3.97410357, 6.25093374, 3.97410357, 3.97410357, 3.97410357, 4.01550048]e-09 → [3.97123023, 6.24641422, 3.97123023, 3.97123023, 3.97123023, 4.01259721]e-09 |

The suite after Task 10: 1569 passed, 2 skipped, no xfail.

**The README's cost excerpt** (Step 2): the controller ran `new` and `cost` on lpf915 into `<P0-2>/tutorial/lpf915`, with `<P0-2>/data` and so P0-A's calibration. The printed Cells line, "Cells: 332 × 195 × 69 = 4.47 M (mesh n 2, cell d 0.0751 mm).", equals README L51, and the RF_B and Main cost lines equal L50 and L54. Worst case and RAM differ only by the calibration: 12 h 34 min for 6 runs, 2 at once with 8 threads each, and about 1.6 GB, against L52–L53's 13 h 16 min, 4 at once with 4 threads each, and about 3.2 GB.

## 4. Decisions

Each decision below applies a controller call.

- **The winner, by condition 5: `1-6_none_served`** (controller recommendation, owner unavailable). Task 6 applied it in `0813f84`: `SLOT_IN = 1/6`, `SLOT_GATE = 0.0` and `SLOT_SERVED = True` in `rule.py`, which `test_the_slot_role_is_plan6s_winner` pins to the grid's literals.
- **No strike** (controller recommendation, owner unavailable). The winner passed every gate-asserting product test, so Task 6's strike rule did not fire and `meshcal.choose` was not rerun. G1 holds (`test_every_fixture_section_passes_the_fit2d_gate`): coupon_gcpw_masked reads 1.05 % at n 2, lpf915 2.33 % and lpf915-45 2.77 %. Task 6 re-pinned the tests whose measured values the rule moved, and marked the two P0 hash tests xfail(strict) until Task 10. The suite read 1566 passed, 2 skipped, 2 xfailed.
- **The guard stays** as part of the searched rule (controller recommendation, owner unavailable). Without it, condition 2 would very likely have rejected all 48 candidates.
- **The harness stays outside the repo**, design §5.1's 'cannot' branch (controller recommendation, owner unavailable). r1's scripts stay in `<R1>`, pinned by sha256 in the committed `meshcal.PINNED`. The boards and the search's tree and raw outputs stay in `<P0-2>/meshcal`.
- **P0-A's branches** (controller recommendation, owner unavailable; `5a5f253`): D-25 pass, D-26 pass, D-27 advice (W_STAIRCASED replaces E_STAIRCASED, with the 4.6 % figure and the n 3 advice), D-28 pass, D-29 keep (the fit2d limit stays 3 %), D-30 confirmed (the floor stays 0.8), verdict pass. The rule stays: the fail branch's revert did not apply.
- **A-8** (controller recommendation, owner unavailable) landed after P0-A's pass, in its own commit `144161a`, in the Stage 1 spec's §5.4 and §12.
- **B1's branch** (controller recommendation, owner unavailable). OQ4's hash check was True, so B1 ran. It ended six converged, so Task 10 took its full branch: lpf915's reference and its six traces were regenerated from B1's record, with the other eight references and the pad coupon's two traces, and the two xfail marks went. B1's dt ratio of 1.1056 is not under 0.85, so Task 11's Step 1 does not apply: D-30 holds over B1 too, and the `GATES` comment stays as Task 8 wrote it.
- **The README** (controller recommendation, owner unavailable). The Cells line did not move, so the excerpt is not edited and no commit is made. D-29 kept the limit, so the tutorial project pins no gates and `cost` printed no W_GATE_LIMITS line.
- **No exit-report addendum** (controller recommendation, owner unavailable): the ceiling, 2026-11-19, applied none of its branches.

## 5. Stated limits and deviations

- **lpf915 and lpf915-45 stay over 3 % at n 3.** Under the winner, lpf915 reads 2.54, 3.433, 4.325, 3.913 and 3.913 %, and lpf915-45 2.443, 3.576, 4.85, 4.017 and 4.056 %. The miss is the step edge, not the slot depth: the role moves RF_A's 0.25 mm section (4.195 → 2.54 % and 4.058 → 2.443 %) and the other sections by +0.002 to +0.003 pp. E_FIT2D_FINE's limit raise remains the remedy (design §3). c1 and G1 leave both out at n 3.
- **The guard reverts a whole axis.** Where one slot line would fail the edge lint or the d/3 merge, or where the slot pass raises a RuntimeError, the whole axis keeps the as-built lines, so every slot edge on it loses its depth.
- **The harness runs at each board's top of band (3 GHz, but for the 14 ms_step boards) with no lid.** Its fit2d reads about 0.05–0.09 pp below the product's 915 MHz projects, which have a lid (r1). The suite's gate tests on 915 MHz projects with lids are the strike rule's check, and the winner passed them.
- **6 of the 1061 boards have no generator** (the six b:ms_pour_vias boards), so the ratchet harness and its boards are not committed. A later calibration re-extracts plan 2's archive.
- **FDTD checks the rule only through P0-A's coupons and B1.** The search is 2D: fit2d on cross-sections, and the axis checks. Full-wave, the calibrated rule ran only in P0-A's 14 coupon runs, its pad coupon and B1's six lpf915 runs.
- **r1's prior probes covered the served scope only**, and came before the guard. The lone scope and the gates 2 and 3 had no prior board-row data.
- **Condition 5's second key reads the GCPW coupons**, condition 4's sections, not §5.1's literal "GCPW families", whose key is degenerate (ruling; controller recommendation, owner unavailable). It decided nothing here: the two candidates with the most passes tie on it at 1.049 %, and the grid's order decided.
- **lpf915's reference:** Task 10 took its full branch, not its lpf915 branch, so lpf915's reference is current under the rule and no stale reference passes to plan 7.
- **Fix commits between runs: none.** The search ran once at `2449427` and P0-A once at `0813f84`, each exiting 0. B1 ran at `ea0ac09`, and its second attempt exited 0. Its first attempt left no record (below), and no commit came between the two attempts. Between them, `src/` and `tools/` changed only through the plan's own decide tasks: Task 6's winner (`0813f84`) and Task 8's pass branch (`5a5f253`).
- **Disclosure.** The plan's controller ruling, as written there: "Controller ruling (disclosure): during this plan's review, one reviewer computed conditions 1 and 4 for all 48 candidates on a scratch tree (condition 1 held for all; condition 4 failed every 3d/16 and 5d/24 candidate). No limit, rule, condition or expectation was changed on that data, and conditions 2 and 3 were not seen." The search measured the same for conditions 1 and 4.
- **The idle check, a minor plan defect.** The second idle check, written with the names `meshcal.py`, `hrun.py` and `launch.py` literally in its `-c` code, matched its own command line and printed [5, 5, 5] with nothing running. From Task 5 on, it ran with the names split (ruling; controller recommendation, owner unavailable), and it found no such process before any run.
- **B1's first attempt**, started on 2026-10-26 at 16:59, did not finish: the session ended overnight, so it left no record. B1 was rerun from scratch on 2026-10-27 at 07:57 on the same code (`ea0ac09`), and the record is the second attempt's. The first attempt's partial run folder stays in `<P0-2>`, and its machine time is not counted.
- **P0-A's own limits** (KiCad's CPWG bias, which leaves the GCPW rows a D-25 margin of 1.8–2.8 pp; A-1; A-2; the oblique εeff) stand as its report states them.

## 6. Machine time

| run | date | predicted | machine hours | ratio |
| --- | --- | --- | --- | --- |
| the search (Task 5), 50 steps | 2026-10-26 | about 5 h | 5.27 | 1.05 |
| P0-A (Task 7), 17 steps | 2026-10-26 | about 3.1 h | 3.58 | 1.16 |
| B1 (Task 9), second attempt | 2026-10-27 | about 3.2 h | 3.91 | 1.22 |
| total | | about 11.3 h | 12.8 | 1.13 |

- The search: `meshcal.json` records 50 steps, none loaded, 5.27 machine hours and 4 elapsed days. That is 6.3 min a step, inside the plan's 6–7 min an evaluation.
- P0-A: `p0a.json` records 17 steps, none loaded, 3.58 machine hours and 4 elapsed days. The plan's 3.1 h did not include the fresh data folder's calibration step. Its report gives the run-by-run times.
- B1: 3.91 h against r4's 3.22 h at reach 3, not loaded. The controller's plan-7 research and design work (CPU-light) went on during B1's attempts.
- Elapsed days: 5 since 2026-10-22 (D-4's count), at B1's end and at this report. The target window is 2026-11-05 to 2026-11-12, and the ceiling 2026-11-19.
- Not counted: B1's first attempt, and the controller's `new` and `cost` run for the README, which runs no FDTD.

## 7. Next step

1. The controller saves this report as `docs/validation/2026-10-27-mesh-calibration.md`, with `meshcal.json` beside it as `2026-10-27-mesh-calibration.json`, runs the privacy gate, commits them, then decides on plan 6 and merges it (design §5.1, step 4).
2. Plan 7 (design §5.2): tails on every reported S (G2, A-9); verify's L with the strips compensated (G3, A-10); the box-term estimator or its registered known difference (A-11); P0-B2 and its pre-registration (G4); P0-D's references again after tails; and the P0-B2 report with its exit-report addendum. B1's new record and P0-A's pad coupon in `<P0-2>` are its independent data.
3. Carried as stated limits: lpf915 and lpf915-45 at n 3, until E_FIT2D_FINE's limit raise. P0-C stays the owner's step.
