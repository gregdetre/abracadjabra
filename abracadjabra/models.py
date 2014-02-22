import random
import types

from datetime import datetime

from django.conf import settings as sett
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import Http404
from django.utils import timezone

from exceptions import SlugAttributeError
from utils.dt import days_in_range, dt_ranges, dt_str, \
    recent_day, recent_week, recent_month, recent_6months, recent_year
from utils.models import QuerySetManager, SoftDeletable, SoftDeletableQuerySet
from utils.utils import isnum, percent, generate_mckey, as_ids


"""
An Experiment is an AB test (e.g. comparing multiple
designs, variants on an algorithm).

For an Experiment, you assign Users randomly to buckets
(variants) by creating an ExperimentUser with the bucket as
a named string. This way, no work is needed to create an
Experiment in advance - just call Experiment.setup().

N.B. Once (randomly assigned to an Experiment bucket), a
user will always be assigned to that bucket.

There are no integrity constraints on bucket types, just strings in
ExperimentUser, to keep things simple.
"""

# xxx what to do if user is not authenticated??? currently
# returns None. better to default to first bucket??? no, i
# think this is better. though it might be useful to know
# that this is happening... assertEmail(user.is_authenticated) in
# setup()?
#
# xxx - ideally, memcache to avoid the Experiment get() in setup()
#
# xxx - perhaps have the buckets in Experiment.setup()
# default to ['control','test']???


class Experiment(SoftDeletable):
    # e.g. 'E1234 - new next button' (where 1234 = Unfuddle ticket)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    cre = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    users = models.ManyToManyField('auth.User', through='ExperimentUser', related_name='experiments')

    objects = QuerySetManager()
    class QuerySet(SoftDeletableQuerySet):
        pass

    class Meta:
        ordering = ('-cre',)

    def __unicode__(self):
        return unicode(self.name)

    def get_absolute_url(self):
        return reverse('experiment_detail', kwargs={'experiment_id': self.id,})

    @staticmethod
    def get_cache_create(name):
        mckey = generate_mckey('experiment', locals())
        cached = cache.get(mckey)
        if cached:
            return cached
        expt, created = Experiment.objects.get_or_create(name=name)
        cache.set(mckey, expt, sett.CACHE_EXPIRY['EXPERIMENT'])
        return expt


    @staticmethod
    def setup(user, name, buckets):
        """
        bucket = Experiment.setup(user,
                                  'E1234 - new next button',
                                  ['control','test 1'])
        if bucket == 'test 1':
            // do it a new way
        elif bucket == 'control':
            // do it the old new way
        else:
            // error - raise Exception
    
            BUCKETS is a list of bucket name strings (these are
        de-normalized and don't get checked, so be careful
        not to mis-type or change the bucket names.]

        See:
        - http://www.startuplessonslearned.com/2008/09/one-line-split-test-or-how-to-ab-all.html
        - main docstring above

        - Check if an Experiment with this name exists. If not, create it.
        - Check if User has already been assigned to a bucket. If so, nothing to do.
        - If the User is not part of this Experiment yet, pick a bucket and create an ExperimentUser.
        - Return bucket name.

        Return None for AnonymousUser.
        """
        if not user.is_authenticated():
            assert False, 'shouldn\'t be running experiment for unauthenticated user'
            return None

        expt = Experiment.get_cache_create(name)
        exptuser = ExperimentUser.get_cache_create(expt, user, buckets)

        assert exptuser.bucket is not None, 'no bucket assigned for %s' % expt.name
        
        # will return already-assigned bucket if existing, otherwise the random one we just picked
        return exptuser.bucket


    def users_in_bucket(self, bucket=None):
        eus = ExperimentUser.objects.filter(experiment=self)
        if bucket:
            eus = eus.filter(bucket=bucket)
        return User.objects.filter(id__in=list(eus.values_list('user__id', flat=True)))
        
    
    def bucket_names(self):
        """
        Returns a sorted list of bucket names for this Experiment.
        """
        # xxx - there has to be a way to get the database to do the set()...?
        names = set(self.exptusers.values_list('bucket', flat=True))
        # since we're going to use 'All' below in COMPUTE_BUCKET
        assert 'All' not in names
        return sorted(list(names))

    def compute_bucket(self, name, dt_joined=None, users=None):
        """
        Computes statistics for the Users in thie
        Experiment, in this BUCKET_NAME, who joined after
        DT_JOINED.

        Excludes staff. Currently includes both anons and signups.
        
        COMPUTE_BUCKETS adds the %_MAX field to the relevant bucket.

        Expects you to have already run CHECK_DT_JOINED().
        """
        if users is None: users = User.objects.all()
        if dt_joined:
            users = users.filter(date_joined__gte=dt_joined)

        if name != 'All':
            expt_users = ExperimentUser.objects \
                .filter(experiment=self, bucket=name) \
                .values_list('user', flat=True)
            users = users.filter(id__in=list(expt_users))

        user_ids = list(users.values_list('id', flat=True))
        return Experiment.compute_metric(name, user_ids)


    @staticmethod
    def compute_metric(name, user_ids):
        """
        Does most of the hard work in COMPUTE_BUCKET.

        However, it can also be run on a bunch of Users
        defined without being part of an Experiment,
        e.g. 'all the Users that have created >=1 Mem'.
        """
        users = User.objects.filter(id__in=user_ids)

        nUsers = users.count()
        users_str = '; '.join(users.values_list('username', flat=True))

        return {'name': name,

                'users_str': users_str,
                'nUsers': nUsers,
                }


    @staticmethod
    def calc_maxes(buckets):
        """
        e.g. if the MEAN_L_PER_U is highest for the 'yes
        send' bucket, then set 'MEAN_L_PER_U_MAX': True
        for that bucket.

        N.B. the other Buckets won't have a METRIC_MAX key.

        Assumes that all the buckets have identical keys.
        """
        # get the metric names for the numerical metrics,
        # e.g. ['nUsers', 'mean_number_of_things_bought_per_user', ...]
        # but not ['users_str']
        metrics = [metric for metric, val in buckets[0].items() if isnum(val)]
        for metric in metrics:
            metric_max = '%s_max' % metric
            # all the values for this METRIC, across Buckets
            vals = [bucket[metric] for bucket in buckets]
            # index of the Bucket with the highest value for METRIC
            max_val = max(vals)
            min_val = min(vals)
            if not isinstance(max_val, (int, float)):
                continue
            if not isinstance(min_val, (int, float)):
                continue
            if not min_val or max_val / float(min_val) < 1.03:
                # [avoid divide-by-zero errors]
                # ignore less than 5% differences, since they're unlikely to be significant
                continue
            idx = vals.index(max_val)
            # add the METRIC_MAX key to that Bucket
            buckets[idx][metric_max] = True
        return buckets

    @classmethod
    def check_dt_joined(cls, cre, dt_joined):
        """
        Make sure DT_JOINED is, at earliest, the beginning
        of this Experiment, so we're only ever analyzing
        users who joined after the Experiment began.
        """
        if isinstance(dt_joined, types.FunctionType):
            dt_joined = dt_joined()
        elif isinstance(dt_joined, (str, unicode)):
            dt_joined = dt_ranges[dt_joined_str][0] # e.g. recent_week()
        assert dt_joined or cre
        dt_joined = dt_joined or cre
        if cre:
            dt_joined = max(dt_joined, cre)
        return dt_joined

    def compute_buckets(self, dt_joined=None, incl_all=False):
        """
        Returns statistics for each BUCKET (including 'All')
        in this Experiment. See COMPUTE_BUCKET.
        """
        dt_joined = Experiment.check_dt_joined(self.cre, dt_joined)
        
        bucket_names = self.bucket_names()
        if incl_all:
            bucket_names += ['All']
        buckets = [self.compute_bucket(bucket_name, dt_joined)
                   for bucket_name in bucket_names]
        buckets = Experiment.calc_maxes(buckets)
        return buckets, dt_joined


class ExperimentUser(models.Model):
    """
    Which Bucket (of which Experiment) does this User belong to?

    See Experiment.setup().
    """
    user = models.ForeignKey('auth.User', related_name='exptusers')
    experiment = models.ForeignKey(Experiment, related_name='exptusers')
    bucket = models.CharField(max_length=100)
    cre = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ('-id',) # CRE isn't indexed, because we want to make this fast to create
        unique_together = ('experiment', 'user',)
    
    def __unicode__(self):
        return u"%s in bucket %s of experiment %s" % (self.user, self.bucket, self.experiment.name)

    @staticmethod
    def get_cache_create(expt, user, buckets):
        mckey = generate_mckey('experiment', locals())
        cached = cache.get(mckey)
        if cached:
            return cached

        exptuser, created = ExperimentUser.objects.get_or_create(experiment=expt, user=user)
        # exptuser.bucket should never be None, but we want to be sure.
        if created or exptuser.bucket is None:
            exptuser.bucket = random.choice(buckets)
            exptuser.save()
            # create a property of Experiment.name with value of bucket_name
            # see http://support.kissmetrics.com/advanced/a-b-testing/running-an-a-b-test (at the bottom)
            # km_set(user, {expt.name: exptuser.bucket})

        cache.set(mckey, exptuser, sett.CACHE_EXPIRY['EXPERIMENTUSER'])
        return exptuser

    @staticmethod
    def get_latest(expt):
        return ExperimentUser.objects.filter(experiment=expt).order_by('-cre')[0]


