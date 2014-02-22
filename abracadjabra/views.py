from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.http import Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext

from exceptions import SlugAttributeError
from models import Experiment, ExperimentUser
from utils.dt import dt_ranges, recent_day, recent_week


@staff_member_required
def experiments_vw(request):
    active_experiments = Experiment.active.all()
    inactive_experiments = Experiment.inactive.all()
    analyses = [] # Analysis.get_all_analyses()
    nAnalyses = len(analyses)
    return render_to_response('abracadjabra/experiments.html',
                              {'active_experiments': active_experiments,
                               'inactive_experiments': inactive_experiments,
                               'analyses': analyses,
                               'nExperiments': Experiment.objects.count(),
                               'nExperimentsActive': active_experiments.count(),
                               'nExperimentsInactive': inactive_experiments.count(),
                               'nAnalyses': nAnalyses,},
                              context_instance=RequestContext(request))


@staff_member_required
def experiment_detail_vw(request, experiment_id):
    dt_joined_str = request.GET.get('dt_joined', 'recent_week')
    dt_joined = dt_ranges[dt_joined_str][0] # e.g. recent_week()
    # use .objects to allow inactive Experiments to still be viewable
    expt = get_object_or_404(Experiment, id=experiment_id)
    buckets, dt_joined = expt.compute_buckets(dt_joined=dt_joined)
    last_exptuser = ExperimentUser.get_latest(expt)
    return render_to_response('abracadjabra/experiment_detail.html',
                              {'expt': expt,
                               'buckets': buckets,
                               'dt_joined': dt_joined,
                               'last_ran': last_exptuser.cre,},
                              context_instance=RequestContext(request))

@staff_member_required
def analysis_detail_vw(request, analysis_slug):
    dt_joined_str = request.GET.get('dt_joined', 'recent_week')
    dt_joined = dt_ranges[dt_joined_str][0] # e.g. recent_week()

    try:
        analysis = Analysis(analysis_slug, dt_joined)
        # and send it by email 60s later, in case this times out
        # send_analysis_mail.apply_async(args=[analysis_slug, analysis.dt_joined],
        #                                countdown=60)
        analysis.run()
    except SlugAttributeError:
        raise Http404

    # for some reason, some of these variables are outside the EXPT scope in experiment_detail.html
    context = {'expt': analysis.as_dict(),
               'dt_joined': analysis.dt_joined,
               'last_ran': None,
               'buckets': analysis.buckets,}

    return render_to_response('abracadjabra/analysis_detail.html',
                              context,
                              context_instance=RequestContext(request))

