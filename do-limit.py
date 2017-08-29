#!/usr/bin/env python

import ROOT as r
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mR", default=350, type=float, help="The resonance mass to test")
    parser.add_argument("--ntoy", default=100, type=int, help="Number of toys")
    parser.add_argument("--npoints", default=5, type=int, help="Number of points to scan in PoI")
    parser.add_argument("--poimax", default=5000, type=float, help="Max PoI value in scan")
    parser.add_argument("--stat-only", action="store_true", help="Do stat only limits.")
    parser.add_argument("--asimov", action="store_true", help="Do asimov limits")
    parser.add_argument("--dataset", default="obsData", help="The dataset to profile to (and treat as observed data)")
    parser.add_argument("workspace", help="the workspace file")
    args = parser.parse_args()

    r.gInterpreter.ProcessLine(".L ExpGaussExp.cxx+")
    #r.gInterpreter.ProcessLine(".L $ROOTSYS/tutorials/roostats/StandardHypoTestInvDemo.C+")
    r.gInterpreter.ProcessLine(".L StandardHypoTestInvDemo.C+")

    #f = r.TFile(args.workspace)
    #w = f.Get("workspace")

    calcType = 2 if args.asimov else 0
    testStat = 3
    useCLs = True

    r.StandardHypoTestInvDemo(args.workspace, "workspace", "ModelConfig", "", args.dataset, calcType, testStat, useCLs, args.mR, args.npoints, 0, args.poimax, args.ntoy, args.stat_only)
    raw_input("Press enter")
