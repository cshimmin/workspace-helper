#!/usr/bin/env python

import ROOT as r
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mR", default=350, type=float, help="The resonance mass to test")
    parser.add_argument("--ntoy", default=100, type=int, help="Number of toys")
    parser.add_argument("workspace", help="the workspace file")
    args = parser.parse_args()

    r.gInterpreter.ProcessLine(".L ExpGaussExp.cxx+")
    #r.gInterpreter.ProcessLine(".L $ROOTSYS/tutorials/roostats/StandardHypoTestInvDemo.C+")
    r.gInterpreter.ProcessLine(".L StandardHypoTestInvDemo.C+")

    #f = r.TFile(args.workspace)
    #w = f.Get("workspace")

    r.StandardHypoTestInvDemo(args.workspace, "workspace", "ModelConfig", "", "obsData", 0, 3, True, args.mR, 5, 0, 5000, args.ntoy)
    raw_input("Press enter")
