#!/usr/bin/env python

import ROOT as r
import sys
import os

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a workspace for the dihiggs analysis")
    parser.add_argument("--allow-missing-systematics", action="store_true", help="don't throw a fit if requested systematics are missing in the systematics file.")
    parser.add_argument("--data", help="path containing observed data to fit to")
    parser.add_argument("--out", help="File to save the workspace to.")
    parser.add_argument("--systematics", help="file containing the systematics for each parameter")
    parser.add_argument("model_template", help="the model workspace template to load")
    args = parser.parse_args()

    w = r.RooWorkspace("workspace")

    mc = r.RooStats.ModelConfig("ModelConfig", w)

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

            sys_names.append(sys_name)

            w.factory("NP_%s[-5,5]"%sys_name)
            w.factory("GLOB_%s[0]"%sys_name)

            if sys_type in ('gauss','bias'):
                w.factory("Gaussian::constr_{name}(NP_{name},GLOB_{name},1)".format(name=sys_name))
            else:
                print>>sys.stderr, "Don't know how to handle systematic type: '%s'"%sys_type
                sys.exit(1)

            for effect in items[2:]:
                assert effect.endswith(')')
                effect = effect[:-1]
                eff_name,eff_size = effect.split('(')
                if not eff_name in systematics:
                    systematics[eff_name] = []
                systematics[eff_name].append((sys_name,float(eff_size),sys_type))

        new_definition = "PROD::constraints({})".format(",".join(["constr_%s"%c for c in sys_names]))
        res = w.factory(new_definition)
        if not res:
            print>>sys.stderr, "Error in line:"
            print>>sys.stderr, new_definition
            sys.exit(1)


    template_file = open(args.model_template)
    observables = {}
    model_pdfs = {}
    poi_names = []
    param_names = []
    for l in template_file:
        l = l.strip()
        #print "'%s'"%l
        if not l or l.startswith("#"): continue
        l = l.split('#')[0]

        if l.startswith("SYS::"):
            l = l[len("SYS::"):]
            
            token_name=l.split('(')[0].split('[')[0]

            systematic_available = token_name in systematics

            if not args.systematics or (not systematic_available and args.allow_missing_systematics):
                print "Note: Ignoring systematics for '%s'"%token_name
                res = w.factory(l)
                if not res:
                    print>>sys.stderr, "Error in line:"
                    print>>sys.stderr, l
                    sys.exit(1)
                continue

            if not token_name in systematics:
                print>>sys.stderr, "Systematics requested for '%s', but none found!"%token_name
                sys.exit(1)
                
            # create a variable (suffixed with _nominal) to hold the nominal value
            new_definition = l.replace(token_name,"%s_nominal"%token_name)
            res = w.factory(new_definition)
            if not res:
                print>>sys.stderr, "Error in line:"
                print>>sys.stderr, new_definition
                sys.exit(1)
            # add an expression that multiplies the nominal value by systematics
            bias_strs = []
            sys_strs = []
            np_names = []
            for sys_name,sys_size,sys_type in systematics[token_name]:
                if sys_type == 'bias':
                    bias_strs.append("%g*NP_%s"%(sys_size,sys_name))
                else:
                    sys_strs.append("(1+%g*NP_%s)"%(sys_size,sys_name))
                np_names.append("NP_%s"%sys_name)
            sys_str = "*".join(sys_strs)
            # and define param as the product of the nominal and systematics
            if bias_strs and sys_strs:
                new_definition = "expr::{name}('({name}_nominal+{biases})*{systs}',{name}_nominal,{np_names})".format(name=token_name,biases='+'.join(bias_strs),systs=sys_str,np_names=','.join(np_names))
            elif bias_strs:
                new_definition = "expr::{name}('{name}_nominal+{biases}',{name}_nominal,{np_names})".format(name=token_name,biases='+'.join(bias_strs),np_names=','.join(np_names))
            else:
                new_definition = "expr::{name}('{name}_nominal*{systs}',{name}_nominal,{np_names})".format(name=token_name,systs=sys_str,np_names=','.join(np_names))
            res = w.factory(new_definition)
            if not res:
                print>>sys.stderr, "Error in line:"
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
                token_name = l.split("::")[1].split('(')[0]
                assert category not in model_pdfs
                model_pdfs[category] = token_name
            elif l.startswith("POI::"):
                l = l[len("POI::"):]
                token_name = l.split('[')[0]
                poi_names.append(token_name)
            elif l.startswith("PARAM::"):
                l = l[len("PARAM::"):]
                token_name = l.split('[')[0]
                param_names.append(token_name)

            res = w.factory(l)
            if not res:
                print>>sys.stderr, "Error in line:"
                print>>sys.stderr, l
                sys.exit(1)

    assert set(observables.keys()) == set(model_pdfs.keys())
    category_names = observables.keys()

    if args.data:
        wt = w.factory("wt[1.0]")

        for cat_name,obs_name in observables.items():
            obs = w.obj(obs_name)

            ds = r.RooDataSet("obsData_%s"%cat_name, "obsData_%s"%cat_name, r.RooArgSet(obs,wt), r.RooFit.WeightVar(wt))
            for l in open(os.path.join(args.data,'%s.txt'%cat_name)):
                x,y = map(float, l.split())
                obs.setVal(x)
                wt.setVal(y)
                ds.add(r.RooArgSet(obs,wt), y)
            getattr(w,'import')(ds)
    else:
        for cat_name in category_names:
            obs = w.obj(observables[cat_name])
            pdf = w.obj(model_pdfs[cat_name])
            ds = pdf.generate(r.RooArgSet(obs))
            ds.SetName("obsData_%s"%cat_name)
            getattr(w,'import')(ds)

    new_definition = "category[%s]"%(','.join(category_names))
    res = w.factory(new_definition)
    if not res:
        print>>sys.stderr, "Error in line:"
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
            print>>sys.stderr, "Error in line:"
            print>>sys.stderr, new_definition
            sys.exit(1)

    assert len(poi_names) == 1
    poi = w.obj(poi_names[0])

    w.defineSet("observables", ",".join(['category']+observables.values()))

    sys_nps = ["NP_%s"%s for s in sys_names]
    sys_globs = ["GLOB_%s"%s for s in sys_names]

    # find nuisance params other than the ones associated w/ systematics
    all_nps = sys_nps[:]
    pdf_vars = top_pdf.getParameters(w.set("observables"))
    itr = pdf_vars.createIterator()
    while True:
        n = itr.Next()
        if not n: break
        if n.isConstant(): continue
        if n.GetName() in sys_globs: continue
        if n.GetName() in sys_nps: continue
        if n.GetName() in poi_names: continue
        if n.GetName() in param_names: continue
        all_nps.append(n.GetName())

    #w.defineSet("nuisanceParams", ",".join(all_nps))
    #w.defineSet("globalObs", ",".join(sys_globs))
    #w.defineSet("POIs", ",".join(poi_names))

    # setup the modelconfig
    mc.SetPdf(top_pdf)
    mc.SetParametersOfInterest(','.join(poi_names))
    mc.SetObservables(w.set("observables"))
    mc.SetNuisanceParameters(','.join(all_nps))
    #mc.SetNuisanceParameters(','.join(sys_nps))
    mc.SetGlobalObservables(','.join(sys_globs))
    getattr(w,'import')(mc)

    # make asimov data in each category
    for cat_name,obs_name in observables.items():
        poival_orig = poi.getVal()
        for muval in (0, 1):
            poi.setVal(muval)
            obs = w.obj(obs_name)
            asimov = r.RooStats.AsymptoticCalculator.GenerateAsimovData(w.obj(model_pdfs[cat_name]), r.RooArgSet(obs))
            asimov.SetName("asimov_mu%d_%s"%(muval,cat_name))
            getattr(w,'import')(asimov)
        poi.setVal(poival_orig)

    ## and one for the simul pdf
    #w.defineSet('observables_plus',','.join(['category']+observables.values()))
    #observables_ = w.set("observables_plus")
    #asimov = r.RooStats.AsymptoticCalculator.GenerateAsimovData(w.obj("pdf_combined"), observables_)
    #asimov.SetName("xdata")
    #getattr(w,'import')(asimov)
    
    # merge the data in each cat into a indexed multi-cat dataset
    obs_vars = r.RooArgSet(*[w.obj(observables[c]) for c in category_names])
    for dstype in ('obsData', 'asimov_mu0', 'asimov_mu1'):
        ds_args = [r.RooFit.Index(w.obj("category"))]
        for cat_name in category_names:
            ds_args += [r.RooFit.Import(cat_name, w.obj("%s_%s"%(dstype,cat_name)))]
        ds_combined = r.RooDataSet(dstype, dstype, obs_vars, *ds_args)
        getattr(w,'import')(ds_combined)

    w.Print()

    if args.out:
        print "Saving workspace to:", args.out
        f = r.TFile(args.out, "recreate")
        f.cd()
        w.Write()
        f.Close()