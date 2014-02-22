from django.conf.urls import patterns, include, url

from django.contrib import admin

import utils.urls_re as ure

admin.autodiscover()


urlpatterns = patterns('abracadjabra.views',
    url(r'^$', 'experiments_vw', name='experiment_experiments'),
    url(r'^%s/$' % ure.experiment_id, 'experiment_detail_vw', name='experiment_detail'),
    # url(r'^analysis/%s/$' % ure.analysis_slug, 'analysis_detail_vw', name='experiment_analysis_detail'),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    )
