# SPDX-License-Identifier: LGPL-3.0-or-later
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015,2016 Thorsten Liebig (Thorsten.Liebig@gmx.de)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# From CSXCAD v0.7.0 (pinned by openEMS-Project v0.37.0), python/CSXCAD/SmoothMeshLines.py; changed 2026-10-20: renamed smooth_mesh_lines, ratio default 1.3, SmoothRange's stop-side step fixed, MeshLinesSymmetric and demo cut.

import numpy as np

def Unique(l, tol=1e-7):
    """
    Internal function, do not use.
    """
    l = np.unique(l)
    dl = np.diff(l)
    idx = np.where(dl<np.mean(dl)*tol)[0]
    if len(idx)>0:
        l = np.delete(l, idx)

    return l

def SmoothRange(start, stop, start_res, stop_res, max_res, ratio):
    """
    Internal function, do not use.
    """
    assert ratio>1
    rng = (stop-start)

    # very small range
    if rng<max_res and rng<start_res*ratio and rng<stop_res*ratio:
        return Unique([start, stop])

    # very large range and easy start/stop res
    if start_res>=(max_res/ratio) and stop_res>=(max_res/ratio):
        N = np.ceil(rng/max_res).astype('int')
        tmp = np.linspace(start, stop, N+1)
        return np.append(np.append(start, tmp[1:-1]), stop)

    def one_side_taper(start_res, ratio, max_res):
        res = start_res
        pos = 0
        N = 0
        while res<max_res and pos<rng:
            res *= ratio
            pos += res
            N += 1
        if pos>rng:
            l = np.zeros(N+1)
            for n in range(N+1):
                l[n] = np.sum(start_res * ratio ** np.arange(1,n+1))
            return l * rng/pos

        _ratio = np.e**((np.log(max_res) - np.log(start_res))/(N))

        l = [0]
        pos = 0
        res = start_res
        for n in range(N):
            res *= _ratio
            pos += res
            l.append(pos)

        while pos<rng:
            pos += max_res
            l.append(pos)

        return np.array(l) * rng/l[-1]

    # need to taper start
    if start_res<(max_res/ratio) and stop_res>=(max_res/ratio):
        tmp = start + one_side_taper(start_res, ratio, max_res)
        return np.append(np.append(start, tmp[1:-1]), stop)

    # need to taper stop
    if start_res>=(max_res/ratio) and stop_res<(max_res/ratio):
        tmp = np.sort(stop - one_side_taper(stop_res, ratio, max_res))
        return np.append(np.append(start, tmp[1:-1]), stop)

    # test if max taper on both sides is possible
    pos1 = 0
    N1 = 0
    res = start_res
    while res<max_res:
        res *= ratio
        pos1 += res
        N1 += 1
    ratio1 = np.e**((np.log(max_res) - np.log(start_res))/(N1))
    pos1 = np.sum(start_res * ratio1 ** np.arange(1,N1+1))

    pos2 = 0
    N2 = 0
    res = stop_res
    while res<max_res:
        res *= ratio
        pos2 += res
        N2 += 1
    ratio2 = np.e**((np.log(max_res) - np.log(stop_res))/(N2))
    pos2 = np.sum(stop_res * ratio2 ** np.arange(1,N2+1))

    if (pos1+pos2)<rng:
        l = [0]
        for n in range(1,N1+1):
            l.append(l[-1]+start_res*ratio1**n)
        r = [0]
        for n in range(1,N2+1):
            r.append(r[-1]+stop_res*ratio2**n)

        left = rng-pos1-pos2
        N = int(np.ceil(left/max_res))

        for n in range(N):
            l.append(l[-1]+max_res)

        length = l[-1]+r[-1]
        c = Unique(np.r_[np.array(l), length-np.array(r)])
        tmp = start + c *rng/length
        return np.append(np.append(start, tmp[1:-1]), stop)

    l = [0]
    r = [0]
    while l[-1]+r[-1]<rng:
        if start_res==stop_res:
            start_res *= ratio
            l.append(l[-1]+start_res)
            stop_res  *= ratio
            r.append(r[-1]+start_res)
        elif start_res<stop_res:
            start_res *= ratio
            l.append(l[-1]+start_res)
        else:
            stop_res  *= ratio
            r.append(r[-1]+stop_res)  # upstream: start_res

    length = l[-1]+r[-1]
    c = Unique(np.r_[np.array(l), length-np.array(r)])
    tmp = start + c *rng/length
    return np.append(np.append(start, tmp[1:-1]), stop)

def CheckSymmetry(lines):
    tolerance = 1e-10
    NP = len(lines)
    if NP<=2:
        return 0
    line_range = lines[-1]-lines[0]
    center = 0.5*(lines[-1]+lines[0])

    # check all lines for symmetry
    for n in range(int(NP/2)):
        if (abs((center-lines[n])-(lines[-n-1]-center)) > line_range*tolerance):
            return 0

    # check central point to be symmetry-center
    if NP%2==1:
        if (abs(lines[int(NP/2)]-center) > line_range*tolerance):
            return 0

    # if all checks pass, return true
    return 2 if NP%2==0 else 1

def SnapToLines(lines, ref, tol=1e-10):
    """
    Internal function, do not use.

    Snap every value in ``lines`` that lies within ``tol`` (relative to the
    total range of ``ref``) of a value in ``ref`` back onto that exact reference
    value. Used to preserve user-supplied fixed mesh lines bit-exactly through
    the mirrored (symmetric) smoothing paths, which otherwise reconstruct them
    from a floating-point center and introduce a ~1 ULP error.
    """
    lines = np.array(lines, dtype=float)
    ref = np.asarray(ref, dtype=float)
    if len(ref)<2:
        return lines
    abs_tol = (ref[-1]-ref[0])*tol
    # nearest reference line for each input line
    idx = np.clip(np.searchsorted(ref, lines), 1, len(ref)-1)
    left  = ref[idx-1]
    right = ref[idx]
    nearest = np.where(lines-left <= right-lines, left, right)
    snap = np.abs(lines-nearest) <= abs_tol
    lines[snap] = nearest[snap]
    return lines

def smooth_mesh_lines(lines, max_res, ratio=1.3, check_symmetry=True, **kw):
    """This is the form of a docstring.

    Parameters
    ----------

    lines : list
        List of mesh lines to be smoothed
    max_res : float
        Maximum allowed resolution, resulting mesh will always stay below that value
    ratio : float
        Ratio of increase or decrease of neighboring mesh lines
    check_symmetry : bool
        If True (default), a symmetric input mesh is detected and only one half
        is smoothed and mirrored. Set to False to disable this detection and
        smooth the full line set directly (e.g. if a coincidentally-symmetric
        mesh should not be treated as symmetric).

    """
    out_l = Unique(lines)
    orig_l = out_l
    sym = CheckSymmetry(out_l) if check_symmetry else 0
    if sym==1:
        center = 0.5*(out_l[-1]+out_l[0])
        out_l = out_l[:int(len(out_l)/2)+1]
    elif sym==2:
        center = 0.5*(out_l[-1]+out_l[0])
        out_l = out_l[:int(len(out_l)/2)]

    dl = np.diff(out_l)

    while len(np.where(dl > max_res * (1 + 1e-10))[0]) > 0:
        N = len(out_l)
        dl[dl<=max_res] = np.max(dl)*2
        idx = np.argmin(dl)
        dl = np.diff(out_l)
        if idx>0:
            start_res = dl[idx-1]
        else:
            start_res = max_res
        if idx<len(dl)-1:
            stop_res = dl[idx+1]
        else:
            stop_res = max_res
        l = SmoothRange(out_l[idx], out_l[idx+1], start_res, stop_res, max_res, ratio)
        out_l = Unique(np.r_[out_l, l])
        dl = np.diff(out_l)

        if len(out_l)==N:
            break

    if sym==1:
        return SnapToLines(Unique(np.r_[out_l, 2*center-out_l[:-1]]), orig_l)
    elif sym==2:
        l = SmoothRange(out_l[-1], 2*center-out_l[-1], dl[-1], dl[-1], max_res, ratio)
        return SnapToLines(Unique(np.r_[out_l, l, 2*center-out_l]), orig_l)
    return Unique(out_l)
