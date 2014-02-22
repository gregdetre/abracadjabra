import datetime

from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.test import TestCase

from abracadjabra.models import Experiment, ExperimentUser
import abracadjabra.settings as exptsett
from utils.dt import recent_week, recent_month
from utils.tests import BaseTests
from utils.utils import percent
  

##############################################################################
class ExperimentTests(BaseTests):
    def setUp(self):
        pass

    def populate_users(self):
        users = []
        for u in range(10):
            username = 'user%i' % u
            user, created = User.objects.get_or_create(username=username,
                                                       email='%s@%s.com' % (username,username),
                                                       password=username)
            users.append(user)
        return users

            
    def test_experiment_setup(self):
        self.assertEqual(Experiment.objects.filter(name='E1').count(), 0)
        self.assertEqual(ExperimentUser.objects.count(), 0)

        nUsers = 500 # exptsett.N_USERS_ALERT + 1
        for u in range(nUsers):
            user = User.objects.create(username='%i' % u, password='%i' % u)
            bucket1 = Experiment.setup(user, 'E1', ['B1a', 'B1b', 'B1c'])
            bucket2 = Experiment.setup(user, 'E1', ['B1a', 'B1b', 'B1c'])
            # if you call Experiment.setup multiple times for the
            # same user, you should get the same BUCKET back each time
            self.assertEqual(bucket1, bucket2)
    
        self.assertEqual(Experiment.objects.filter(name='E1').count(), 1)
        self.assertEqual(ExperimentUser.objects.count(), nUsers)
        
        buckets = {'B1a': ExperimentUser.objects.filter(bucket='B1a').count(),
                   'B1b': ExperimentUser.objects.filter(bucket='B1b').count(),
                   'B1c': ExperimentUser.objects.filter(bucket='B1c').count(),}
        # confirm that new users are getting assigned to buckets randomly
        tol = 100 # each bucket should have within TOL users of the others. ARBITRARY
        self.assertTrue(max(buckets.values()) - min(buckets.values()) <= tol)


    def test_authenticated(self):
        user = AnonymousUser()
        self.assertEqual(Experiment.setup(user, 'E1', ['B1a', 'B1b', 'B1c']), None)
        

    def test_bucket_names(self):
        expt = Experiment.objects.create(name='E1')
        users = list(self.populate_users())
        self.assertEqual(expt.bucket_names(), [])
        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='bucket1')
        self.assertEqual(expt.bucket_names(), ['bucket1'])
        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='bucket2')
        self.assertEqual(expt.bucket_names(), ['bucket1', 'bucket2'])
        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='bucket1')
        self.assertEqual(expt.bucket_names(), ['bucket1', 'bucket2'])
        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='bucket3')
        self.assertEqual(expt.bucket_names(), ['bucket1', 'bucket2', 'bucket3'])
        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='bucket2')
        self.assertEqual(expt.bucket_names(), ['bucket1', 'bucket2', 'bucket3'])

        eu = ExperimentUser.objects.create(user=users.pop(), experiment=expt, bucket='All')
        with self.assertRaises(AssertionError):
            expt.bucket_names()
        
            
    def test_compute_bucket(self):
        User.objects.all().delete()
        expt = Experiment.objects.create(name='E1')
        good_user1 = self.create_user('_good_user1') # anon
        good_user2 = self.create_user('good_user2')
        good_user3 = self.create_user('good_user3')
        bad_user1 = self.create_user('_bad_user1') # anon
        bad_user2 = self.create_user('bad_user2')
        extra_user = self.create_user('extra_user') # not part of Experiment
        eu = ExperimentUser.objects.create(user=good_user1, experiment=expt, bucket='good')
        eu = ExperimentUser.objects.create(user=good_user2, experiment=expt, bucket='good')
        eu = ExperimentUser.objects.create(user=good_user3, experiment=expt, bucket='good')
        eu = ExperimentUser.objects.create(user=bad_user1, experiment=expt, bucket='bad')
        eu = ExperimentUser.objects.create(user=bad_user2, experiment=expt, bucket='bad')
        good_bucket = expt.compute_bucket('good')
        self.assertEqual(good_bucket['nUsers'], 3)
        bad_bucket = expt.compute_bucket('bad')
        self.assertEqual(bad_bucket['nUsers'], 2)

        # now, if we pretend these users joined ages ago and
        # filter by DT_JOINED, none of them should count
        good_users = expt.users_in_bucket('good')
        for user in good_users:
            user.date_joined -= datetime.timedelta(days=365)
            user.save()
        good_bucket = expt.compute_bucket('good', dt_joined=recent_week())
        self.assertEqual(good_bucket['nUsers'], 0)


    def test_calc_maxes(self):
        """
        Test that it's figuring out which bucket wins each
        metric, or if there are no winners.
        """
        def assertWinner(buckets, idx, metric):
            for b,bucket in enumerate(buckets):
                metric_max = '%s_max' % metric
                # the IDX^th bucket has MAX
                if b == idx:
                    self.assertTrue(buckets[b].get(metric_max))
                else:
                    # and none of the other buckets do
                    self.assertFalse(buckets[b].get(metric_max))


        buckets = [
            {'metric1':   10,
             'metric2':  100,
             'metric3': 1000,},
            {'metric1':    5,
             'metric2':  300,
             'metric3': 1001,},
            {'metric1':    8,
             'metric2':  200,
             'metric3':  999,},
            ]
        buckets = Experiment.calc_maxes(buckets)
        bucket1 = buckets[0]
        bucket2 = buckets[1]
        bucket3 = buckets[2]
        # BUCKET 1 wins 'metric1'
        assertWinner(buckets, 0, 'metric1')
        # BUCKET 2 wins 'metric2'
        assertWinner(buckets, 1, 'metric2')
        # BUCKET 3 wins 'metric3', but not by a big enough
        # margin, so nobody's max
        assertWinner(buckets, None, 'metric3')


    def test_experimentuser_caching(self):
        user1 = self.create_user('good_user1')
        user2 = self.create_user('good_user2')
        user3 = self.create_user('good_user3')

        e1a = Experiment.get_cache_create(name='E1')
        e1b = Experiment.get_cache_create(name='E1')
        self.assertEqual(e1a, e1b)
        e2 = Experiment.get_cache_create(name='E2')

        buckets1 = ['b1a', 'b1b',]
        buckets2 = ['b2a', 'b2b', 'b2c',]
        
        eu11 = ExperimentUser.get_cache_create(expt=e1a, user=user1, buckets=buckets1)
        eu12 = ExperimentUser.get_cache_create(expt=e1a, user=user2, buckets=buckets1)
        eu13 = ExperimentUser.get_cache_create(expt=e1a, user=user3, buckets=buckets1)
        eu23 = ExperimentUser.get_cache_create(expt=e2, user=user2, buckets=buckets2)

        self.assertEqual(Experiment.objects.count(), 2)
        self.assertEqual(ExperimentUser.objects.count(), 4)

        self.assertEqual(eu11, ExperimentUser.get_cache_create(expt=e1a, user=user1, buckets=buckets1))
        self.assertEqual(eu12, ExperimentUser.get_cache_create(expt=e1a, user=user2, buckets=buckets1))
        self.assertEqual(eu13, ExperimentUser.get_cache_create(expt=e1a, user=user3, buckets=buckets1))
        self.assertEqual(eu23, ExperimentUser.get_cache_create(expt=e2, user=user2, buckets=buckets2))

        # if you change the buckets being input (not a good
        # idea), it won't use the cache any more, but it'll
        # still return the right answer
        self.assertEqual(eu11, ExperimentUser.get_cache_create(expt=e1a, user=user1, buckets=buckets2))
        # self.assertEqual(eu23.)


