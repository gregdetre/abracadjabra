"""
Embed these in urls.py, e.g.

  url(r'^stats/(?P<username>[a-zA-Z0-9 @+\._-]+)/$', 'user_stats_vw', name='stats'),

  ->
  
  import utils.urls_re as ure
  # standard replacement of username
  url(r'^stats/%s/$' % ure.username, 'user_stats_vw', name='user_stats'),

  # if you have the same slug appearing twice
  url(r'^merge_in_item_keep_discard/(?P<keep_slug>%s)/(?P<discard_slug>%s)/$' %
        (ure.slug_re,ure.slug_re), 'merge_in_item_keep_discard_vw', name='merge_in_item_keep_discard'),

  # to test
  from django.core.urlresolvers import reverse
  reverse('merge_in_item_keep_discard', keep_slug='blah', discard_slug='blah')

This way, if we ever need to change the regexes, we can do it in one place.
"""

id_re = r'\d+'
slug_re = r'[a-zA-Z0-9_-]+'
key_re = r'\w+'
token_re = r'.+'
uidb36_re = r'[0-9A-Za-z]+'
username_re = r'[\w.-]+' # See settings.SOCIAL_AUTH_PROCESS_USERNAME_FUNC
dt_range_re = r'[a-zA-Z0-9 @+\._-]+'

key = r'(?P<key>%s)' % key_re
user_id = r'(?P<user_id>%s)' % id_re
username = r'(?P<username>%s)' % username_re
experiment_id = r'(?P<experiment_id>%s)' % id_re 
analysis_slug = r'(?P<analysis_slug>%s)' % slug_re
