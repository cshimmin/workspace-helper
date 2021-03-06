#!/usr/bin/env python

import ROOT as r
import sys
import os
import numpy as np

def factory(w, expr, line_no=None):
    res = w.factory(expr)
    if not res:
        if line_non is not None:
            print>>sys.stderr, "Error on L%d"%(line_number)
        else:
            print>>sys.stderr, "Error processing line"
        print>>sys.stderr, expr
        sys.exit(1)
    return res

def iterset(varset):
    itr = varset.createIterator()
    while True:
        x = itr.Next()
        if not x: break
        yield x

def set_const(varset, const=True):
    for x in iterset(varset):
        x.setConstant(const)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a workspace for the dihiggs analysis")
    parser.add_argument("--allow-missing-systematics", action="store_true", help="don't throw a fit if requested systematics are missing in the systematics file.")
    parser.add_argument("--data", help="path containing observed data to fit to")
    parser.add_argument("--out", help="File to save the workspace to.")
    parser.add_argument("--systematics", help="file containing the systematics for each parameter")
    parser.add_argument("--stat-only", action="store_true", help="Do stat-only limits (set NPs and GLOBs to constant)")
    parser.add_argument("--wsname", default="workspace", help="The name of the workspace to create")
    parser.add_argument("--mcname", default="ModelConfig", help="The name of the model config to create")
    parser.add_argument("--profiledata", action="store_true", help="do an initial background-only fit to the data")
    parser.add_argument("--injection", default=[], action="append", help="Signal injection point to append")
    parser.add_argument("model_template", help="the model workspace template to load")
    args = parser.parse_args()

    w = r.RooWorkspace(args.wsname)

    mc = r.RooStats.ModelConfig(args.mcname, w)

    systematics = {}
    sys_names = []
    if args.systematics:
        for l in open(args.systematics):
            l = l.split('#')[0]
            l = l.strip()
            if not l or l.startswith('#'): continue

            items = l.split()
            sys_name = items[0]
            sys_type = items[1]



            if sys_type in ('gauss','bias','logn'):
                if not sys_name in sys_names:
                    sys_names.append(sys_name)
                    print "making nuisance param: NP_%s"%sys_name
                    w.factory("NP_%s[-5,5]"%sys_name)
                    w.factory("GLOB_%s[-5,5]"%sys_name)
                    w.obj("GLOB_%s"%sys_name).setConstant(True)
                    w.factory("Gaussian::constr_{name}(NP_{name},GLOB_{name},1)".format(name=sys_name))
                
                for affected_param in items[2:]:
                    assert affected_param.endswith(')')
                    affected_param = affected_param[:-1]
                    param_name,eff_size = affected_param.split('(')
                    if not param_name in systematics:
                        systematics[param_name] = []
                    systematics[param_name].append((sys_name,float(eff_size),sys_type))

            else:
                print>>sys.stderr, "Don't know how to handle systematic type: '%s'"%sys_type
                sys.exit(1)


        new_definition = "PROD::constraints({})".format(",".join(["constr_%s"%c for c in sys_names]))
        res = w.factory(new_definition)
        if not res:
            print>>sys.stderr, "Error on L%d:"%(line_number + 1)
            print>>sys.stderr, new_definition
            sys.exit(1)


    template_file = open(args.model_template)
    observables = {}
    model_pdfs = {}
    poi_names = []
    cparam_names = []
    for line_number,l in enumerate(template_file):
        l = l.strip()
        #print "'%s'"%l
        if not l or l.startswith("#"): continue
        l = l.split('#')[0]

        if l.startswith("CXX::"):
            # load in a CXX file requested as a dependence
            classname = l.split("::")[1]
            cxxfile = classname + ".cxx"
            print "Loading dependency: %s" % cxxfile
            load_result = r.gInterpreter.ProcessLine(".L %s+"%cxxfile)
            if not load_result == 0:
                print>>sys.stderr, "Error loading file: %s" % cxxfile
                sys.exit(1)
            #w.importClassCode(getattr(r,classname).Class(), True)
        elif l.startswith("SYS::"):
            l = l[len("SYS::"):]
            
            token_name=l.split('(')[0].split('[')[0]
            if '::' in token_name:
                token_name = token_name.split('::')[1]

            systematic_available = token_name in systematics

            if not args.systematics or (not systematic_available and args.allow_missing_systematics):
                print "Note: Ignoring systematics for '%s'"%token_name
                res = w.factory(l)
                if not res:
                    print>>sys.stderr, "Error on L%d:"%(line_number+1)
                    print>>sys.stderr, l
                    sys.exit(1)
                continue

            if not token_name in systematics:
                print>>sys.stderr, "Systematics requested for '%s', but none found!"%token_name
                sys.exit(1)

            # create a variable (suffixed with _nominal) to hold the nominal value
            new_definition = l.replace(token_name,"%s_nominal"%token_name)
            res = factory(w,new_definition,line_number+1)

            # add an expression that multiplies the nominal value by systematics
            # (or adds the systematic in the case of a bias)
            bias_strs = []
            sys_strs = []
            arg_names = []
            for sys_name,sys_size,sys_type in systematics[token_name]:
                # make a constant variable to hold the magnitude of the systematic
                uncert_name = "%s_uncert_%s"%(token_name,sys_name)
                factory(w,"%s[%g]"%(uncert_name, sys_size))
                if sys_type == 'bias':
                    bias_strs.append("%s*NP_%s"%(uncert_name,sys_name))
                elif sys_type == 'gauss':
                    sys_strs.append("(1+%s*NP_%s)"%(uncert_name,sys_name))
                elif sys_type == 'logn':
                    sys_strs.append("exp(sqrt(log(1+%s*%s))*NP_%s)"%(uncert_name,uncert_name,sys_name))
                arg_names.append("NP_%s"%sys_name)
                arg_names.append(uncert_name)

            sys_str = "*".join(sys_strs)
            # and define param as the product of the nominal and systematics
            if bias_strs and sys_strs:
                new_definition = "expr::{name}('({name}_nominal+{biases})*{systs}',{name}_nominal,{arg_names})".format(name=token_name,biases='+'.join(bias_strs),systs=sys_str,arg_names=','.join(arg_names))
            elif bias_strs:
                new_definition = "expr::{name}('{name}_nominal+{biases}',{name}_nominal,{arg_names})".format(name=token_name,biases='+'.join(bias_strs),arg_names=','.join(arg_names))
            else:
                new_definition = "expr::{name}('{name}_nominal*{systs}',{name}_nominal,{arg_names})".format(name=token_name,systs=sys_str,arg_names=','.join(arg_names))
            res = w.factory(new_definition)
            if not res:
                print>>sys.stderr, "Error on L%d:"%(line_number+1)
                print>>sys.stderr, new_definition
                sys.exit(1)
            print new_definition
        else:
            if l.startswith("OBS("):
                obs_tag = l.split("::")[0]
                assert obs_tag.endswith(')')
                category = obs_tag[len("OBS("):-1]
                l = l[len(obs_tag)+2:]
                token_name = l.split('[')[0]
                assert category not in observables
                observables[category] = token_name
            elif l.startswith("MODEL("):
                mod_tag = l.split("::")[0]
                assert mod_tag.endswith(")")
                category = mod_tag[len("MODEL("):-1]
                l = l[len(mod_tag)+2:]
                if '::' in l:
                    token_name = l.split("::")[1].split('(')[0]
                else:
                    token_name = l
                assert category not in model_pdfs
                model_pdfs[category] = token_name
            elif l.startswith("POI::"):
                l = l[len("POI::"):]
                token_name = l.split('[')[0]
                poi_names.append(token_name)
            elif l.startswith("PARAM::"):
                l = l[len("PARAM::"):]
                token_name = l.split('[')[0]
                cparam_names.append(token_name)

            res = w.factory(l)
            if not res:
                print>>sys.stderr, "Error on L%d:"%(line_number+1)
                print>>sys.stderr, l
                sys.exit(1)

    assert set(observables.keys()) == set(model_pdfs.keys())
    category_names = observables.keys()

    if args.data:
        wt = w.factory("wt[1.0]")

        for cat_name,obs_name in observables.items():
            obs = w.obj(obs_name)

            ds = r.RooDataSet("obsData_%s"%cat_name, "obsData_%s"%cat_name, r.RooArgSet(obs,wt), r.RooFit.WeightVar(wt))
            indata = np.loadtxt(os.path.join(args.data,'%s.txt'%cat_name))
            if indata.ndim == 1:
                # assume weights of 1.0
                indata = np.vstack([indata, np.ones_like(indata)]).T
            for x,y in indata:
                # restrict to the range of the observable
                if x<obs.getMin() or x>obs.getMax(): continue

                obs.setVal(x)
                wt.setVal(y)
                ds.add(r.RooArgSet(obs,wt), y)
            getattr(w,'import')(ds)

    # generate datasets, with PoI set to zero
    poi = w.obj(poi_names[0])
    poival_orig = poi.getVal()
    poi.setVal(0)
    for cat_name in category_names:
        obs = w.obj(observables[cat_name])
        pdf = w.obj(model_pdfs[cat_name])
        ds = pdf.generate(r.RooArgSet(obs))
        ds.SetName("pseudoData_%s"%cat_name)
        getattr(w,'import')(ds)
    poi.setVal(poival_orig)

    new_definition = "category[%s]"%(','.join(category_names))
    res = w.factory(new_definition)
    if not res:
        print>>sys.stderr, "Error on L%d:"%(line_number+1)
        print>>sys.stderr, new_definition
        sys.exit(1)

    top_pdf = r.RooSimultaneous("pdf_combined", "pdf_combined", w.obj("category"))
    for cat_name in category_names:
        top_pdf.addPdf(w.obj(model_pdfs[cat_name]), cat_name)
    getattr(w,'import')(top_pdf)

    if args.systematics:
        new_definition = "PROD::pdf_constr(pdf_combined,constraints)"
        top_pdf = w.factory(new_definition)
        if not top_pdf:
            print>>sys.stderr, "Error on L%d:"%(line_number+1)
            print>>sys.stderr, new_definition
            sys.exit(1)

    #assert len(poi_names) == 1
    assert len(poi_names) > 0
    poi = w.obj(poi_names[0])

    w.defineSet("observables", ",".join(['category']+observables.values()))

    sys_nps = ["NP_%s"%s for s in sys_names]
    sys_globs = ["GLOB_%s"%s for s in sys_names]

    # find nuisance params other than the ones associated w/ systematics
    #all_nps = sys_nps[:]
    pdf_vars = top_pdf.getParameters(w.set("observables"))
    itr = pdf_vars.createIterator()
    other_nps = []
    while True:
        n = itr.Next()
        if not n: break
        if n.isConstant(): continue
        if n.GetName() in sys_globs: continue
        if n.GetName() in sys_nps: continue
        if n.GetName() in poi_names: continue
        if n.GetName() in cparam_names: continue
        other_nps.append(n.GetName())

    all_nps = sys_nps + other_nps

    w.defineSet("nonSysParameters", ",".join(other_nps))

    # setup the modelconfig
    mc.SetPdf(top_pdf)
    mc.SetParametersOfInterest(','.join(poi_names))
    mc.SetObservables(w.set("observables"))
    if args.stat_only:
        if other_nps:
            mc.SetNuisanceParameters(','.join(other_nps))
    else:
        mc.SetNuisanceParameters(','.join(all_nps))
        mc.SetGlobalObservables(','.join(sys_globs))
    #mc.SetConditionalObservables(','.join(cparam_names))
    getattr(w,'import')(mc)

    w.saveSnapshot("nps_init", mc.GetNuisanceParameters())
    w.saveSnapshot("globs_init", mc.GetGlobalObservables())

    if args.stat_only:
        for v in sys_nps+sys_globs:
            w.obj(v).setConstant(True)


    # make asimov data in each category
    for cat_name,obs_name in observables.items():
        poival_orig = poi.getVal()
        for muval in (0, 1):
            poi.setVal(muval)
            obs = w.obj(obs_name)
            nbins = obs.getBins()
            obs.setBins(800)
            asimov = r.RooStats.AsymptoticCalculator.GenerateAsimovData(w.obj(model_pdfs[cat_name]), r.RooArgSet(obs))
            asimov.SetName("asimovDataMu%d_%s"%(muval,cat_name))
            getattr(w,'import')(asimov)
            obs.setBins(nbins)
        poi.setVal(poival_orig)

    if args.profiledata:
        poi.setVal(0)
        poi.setConstant(True)

    ## and one for the simul pdf
    w.defineSet('observables_plus',','.join(['category']+observables.values()))
    observables_ = w.set("observables_plus")
    poival_orig = poi.getVal()
    for muval in (0, 1):
        # save the bin numbers for the observables, and termporarily re-set them
        nbins = {}
        for cat_name,obs_name in observables.items():
            nbins[cat_name] = w.obj(obs_name).getBins()
            w.obj(obs_name).setBins(800)

        poi.setVal(muval)
        asimov = r.RooStats.AsymptoticCalculator.GenerateAsimovData(w.obj("pdf_combined"), observables_)
        asimov.SetName("asimovDataMu%d"%muval)
        getattr(w,'import')(asimov)

        # set observable bin counts back to original vals
        for cat_name,obs_name in observables.items():
            w.obj(obs_name).setBins(nbins[cat_name])
    poi.setVal(poival_orig)
    
    # merge the data in each cat into a indexed multi-cat dataset
    for dstype in ('obsData', 'pseudoData',):
        obs_vars = r.RooArgSet(*[w.obj(observables[c]) for c in category_names])
        ds_args = [r.RooFit.Index(w.obj("category"))]
        if dstype == 'obsData':
            if not args.data: continue
            obs_vars.add(w.obj("wt"))
            ds_args.append(r.RooFit.WeightVar(w.obj("wt")))
        for cat_name in category_names:
            ds_args += [r.RooFit.Import(cat_name, w.obj("%s_%s"%(dstype,cat_name)))]
        ds_combined = r.RooDataSet(dstype, dstype, obs_vars, *ds_args)
        getattr(w,'import')(ds_combined)

    poival_orig = poi.getVal()
    poi.setVal(0)
    poi.setConstant(True)
    for i in xrange(10):
        obs_vars = r.RooArgSet(w.obj("category"),*[w.obj(observables[c]) for c in category_names])
        ds_again = top_pdf.generate(obs_vars)
        ds_again.SetName("pdata_%d"%i)
        getattr(w,'import')(ds_again)

    for inj in args.injection:
        w.loadSnapshot("nps_init")
        assignments = inj.split(",")
        inj_name = ""
        for assignment in assignments:
            name,val = assignment.split("=")
            w.obj(name).setVal(float(val))
            inj_name += "_%s_%g"%(name, float(val))
        for i in xrange(20):
            obs_vars = r.RooArgSet(w.obj("category"),*[w.obj(observables[c]) for c in category_names])
            ds = top_pdf.generate(obs_vars)
            ds.SetName("idata_%d"%i+inj_name)
            getattr(w,'import')(ds)


    poi.setVal(poival_orig)
    poi.setConstant(False)


    # import any code that we loaded
    w.importClassCode("*")
    w.Print()

    if args.out:
        print "Saving workspace to:", args.out
        f = r.TFile(args.out, "recreate")
        f.cd()
        w.Write()
        f.Close()
