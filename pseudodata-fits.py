#!/usr/bin/env python

import ROOT as r
from glob import glob
import os
import sys
import argparse
import numpy as np

# record the 1/2-tag expectation variable names as they appaer in the workspace, and corresponding the 1/2-tag nuisance params,
# as well as a reasonable range to use for the variables in the case they are free in the fit
WORKSPACE_VARIABLES = {
        'norm': {
            'expected': ('nbkg_fit_bj_bj', 'nbkg_fit_bb_bb'),
            'NPs': ('bkg_constraint_bj', 'bkg_constraint_bb'),
            'uncert': ('sigma_Const_bj_bj', 'sigma_Const_bb_bb'),
            'range': ( (1, 300), (1, 100) ),
            },
        'peak': {
            'expected': ('novosibirsk_peak_bj', 'novosibirsk_peak_bb'),
            'NPs': ('bkg_constraint_shape_bj', 'bkg_constraint_shape_bb'),
            'uncert': ('sigma_Const_shape_bj_bj', 'sigma_Const_shape_bb_bb'),
            'range': ( (250, 280), (250, 280) ),
            },
        'width': {
            'expected': ('novosibirsk_width_bj', 'novosibirsk_width_bb'),
            'NPs': ('bkg_constraint_width_bj', 'bkg_constraint_width_bb'),
            'uncert': ('sigma_Const_width_bj_bj', 'sigma_Const_width_bb_bb'),
            'range': ( (10, 40), (10, 40) ),
            },
        'tail': {
            'expected': ('novosibirsk_tail_bj', 'novosibirsk_tail_bj'),
            'NPs': ('bkg_constraint_tail_bj', 'bkg_constraint_tail_bb'),
            'uncert': ('sigma_Const_tail_bj_bj', 'sigma_Const_tail_bb_bb'),
            'range':( (-5, -0.1), (-5, -0.1) ),
            },
        }

# helper function that configure a certain variable (norm, peak, width, tail) to be either fixed,
# constrained, or free during the workspace fits. it gets expected values, uncertainties, etc
# from the command line arguments.
def configure_var(w, varname, args):
    # get the requested values from the commandline args
    mode = getattr(args, "bg_%s_mode"%varname)
    expected = getattr(args, "bg_%s_expected"%varname)
    uncert = getattr(args, "bg_%s_uncert"%varname)

    if not mode in ('fixed', 'free', 'constr'):
        raise ValueError("unknown variable mode: %s" % mode)

    # get a list of the variables and nuisance paramters corresponding to the selected variable (peak, width, etc)
    var_1tag, var_2tag = WORKSPACE_VARIABLES[varname]['expected']
    np_1tag, np_2tag = WORKSPACE_VARIABLES[varname]['NPs']
    uncert_1tag, uncert_2tag = WORKSPACE_VARIABLES[varname]['uncert']

    # first, set the expected level of the variable, regardless of the mode
    w.obj(var_1tag).setVal(expected[0])
    w.obj(var_2tag).setVal(expected[1])

    if mode in ('fixed', 'free'):
        # disable NP's in either fixed or free mode
        w.obj(np_1tag).setVal(0)
        w.obj(np_1tag).setConstant(True)
        w.obj(np_2tag).setVal(0)
        w.obj(np_2tag).setConstant(True)
    else:
        # make sure NPs are free in constrained mode,
        # and set the uncertainty level
        w.obj(np_1tag).setConstant(False)
        w.obj(np_2tag).setConstant(False)
        w.obj(uncert_1tag).setVal(uncert[0])
        w.obj(uncert_1tag).setVal(uncert[1])

    if mode == 'free':
        # in free mode, need to make sure the expected level is not constant
        # and give it a range
        w.obj(var_1tag).setConstant(False)
        w.obj(var_1tag).setRange(*WORKSPACE_VARIABLES[varname]['range'][0])
        w.obj(var_2tag).setConstant(False)
        w.obj(var_2tag).setRange(*WORKSPACE_VARIABLES[varname]['range'][1])

def make_dataset(sample_path, w):
    obs = w.obj("gg_mass")
    cat = w.obj("channellist")

    # pick a file and get the unique sample name from its prefix
    sample_name = os.path.basename(glob(os.path.join(sample_path, "*lowMass_1tag.txt"))[0]).split("_lowMass")[0]
    print sample_name

    d1 = np.loadtxt(glob(os.path.join(sample_path, "*lowMass_1tag.txt"))[0])
    d2 = np.loadtxt(glob(os.path.join(sample_path, "*lowMass_2tag.txt"))[0])

    ds1 = r.RooDataSet(sample_name+"_1", sample_name+"_1", r.RooArgSet(obs))
    ds2 = r.RooDataSet(sample_name+"_2", sample_name+"_2", r.RooArgSet(obs))

    for x in d1:
        # restrict to the range of the observable
        if x<obs.getMin() or x>obs.getMax(): continue
        obs.setVal(x)
        ds1.add(r.RooArgSet(obs))

    for x in d2:
        # restrict to the range of the observable
        if x<obs.getMin() or x>obs.getMax(): continue
        obs.setVal(x)
        ds2.add(r.RooArgSet(obs))

    #print "NBG1:", ds1.sumEntries()
    #print "NBG2:", ds2.sumEntries()

    # merge the datasets
    ds_combined = r.RooDataSet(sample_name, sample_name, r.RooArgSet(obs), r.RooFit.Index(cat), r.RooFit.Import("bj", ds1), r.RooFit.Import("bb", ds2))

    return ds_combined

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws", required=True, help="The workspace file")
    parser.add_argument("--indata", required=True, help="Path containing pseudodata from James")
    parser.add_argument("--out", help="The numpy file to save results to")

    parser.add_argument("--obs-min", type=float, default=245, help="The lower limit of the observable (default: %(default)s)")
    parser.add_argument("--obs-max", type=float, default=610, help="The upper limit of the observable (default: %(default)s)")
    parser.add_argument("--mX", type=int, default=300, help="The resonance mass hypothesis (default: %(default)s)")

    parser.add_argument("--bg-norm-mode", choices=("constr", "fixed", "free"), default="constr", help="Mode for non-Higgs BG normalization (default: %(default)s)")
    parser.add_argument("--bg-norm-expected", nargs=2, type=float, default=(111.93, 20.53), help="The expected non-Higgs BG normalization in 1- and 2-tag (default: %(default)s)")
    parser.add_argument("--bg-norm-uncert", nargs=2, type=float, default=(0.1, 0.2), help="The uncertainty in non-Higgs BG normalization in 1- and 2-tag (default: %(default)s)")

    parser.add_argument("--bg-peak-mode", choices=("constr", "fixed", "free"), default="constr", help="Mode for BG peak (default: %(default)s)")
    parser.add_argument("--bg-peak-expected", nargs=2, type=float, default=(273, 266), help="The expected BG peak in 1- and 2-tag (default: %(default)s)")
    parser.add_argument("--bg-peak-uncert", nargs=2, type=float, default=(0.025, 0.025), help="The uncertainty in BG peak in 1- and 2-tag (default: %(default)s)")

    parser.add_argument("--bg-width-mode", choices=("constr", "fixed", "free"), default="constr", help="Mode for BG width (default: %(default)s)")
    parser.add_argument("--bg-width-expected", nargs=2, type=float, default=(35.4, 31.7), help="The expected BG width in 1- and 2-tag (default: %(default)s)")
    parser.add_argument("--bg-width-uncert", nargs=2, type=float, default=(0.189, 0.52), help="The uncertainty in BG width in 1- and 2-tag (default: %(default)s)")

    parser.add_argument("--bg-tail-mode", choices=("constr", "fixed", "free"), default="constr", help="Mode for BG tail (default: %(default)s)")
    parser.add_argument("--bg-tail-expected", nargs=2, type=float, default=(-1.48, -3.3), help="The expected BG tail in 1- and 2-tag (default: %(default)s)")
    parser.add_argument("--bg-tail-uncert", nargs=2, type=float, default=(0.5, 0.5), help="The uncertainty in BG tail in 1- and 2-tag (default: %(default)s)")

    args = parser.parse_args()

    # load up the workspace, modelconfig, etc
    f0 = r.TFile(args.ws)
    w = f0.Get("combination")
    mc = w.obj("mconfig")
    
    obs = w.obj("gg_mass")
    cat = w.obj("channellist")
    poi = w.obj("npbBSM")
    mX = w.obj("mHiggs")

    pdf = mc.GetPdf()
    pdf.Print()

    # set the hypothesis resonance mass
    mX.setVal(args.mX)

    # set the range for the lowmass observable
    obs.setMin(args.obs_min)
    obs.setMax(args.obs_max)

    # load in the pseudodata and create RooDataSets
    sample_paths = sorted(glob(os.path.join(args.indata, "sample_*")))
    datasets = []
    for sample_path in sample_paths[:40]:
        datasets.append(make_dataset(sample_path, w))


    # configure the variables in the workspace
    configure_var(w, 'norm', args)
    configure_var(w, 'peak', args)
    configure_var(w, 'width', args)
    configure_var(w, 'tail', args)

    # numpy dtype to create named columns in output file
    dtype = [
            ('poi', float),
            ('poi_up', float),
            ('poi_down', float),
            ]

    fit_results = []
    for ds in datasets:
        # make the likelihood for this dataset
        nll = pdf.createNLL(ds)

        # minimize it
        minimizer = r.RooMinuit(nll)
        minimizer.migrad()
        minimizer.minos()

        fit_results.append( (poi.getVal(), poi.getAsymErrorHi(), poi.getAsymErrorLo()) )
        if args.out:
            np.save(args.out, np.array(fit_results, dtype=dtype))
