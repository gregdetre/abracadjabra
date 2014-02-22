from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client


def as_ids(lst, sort=True):
    """
    Returns the IDs for all the objects in the list/QuerySet, to
    make it easier to compare lists of objects and lists
    of dictionaries.

    I wanted this as a standalone function to make it terser to call.

    e.g. self.assertEqual(do_search({'word': 'aaa bbb ccc'}),
                          as_ids([item1, item2], sort=False))

    see also utils.utils.as_ids()
    """
    ids = []
    for x in lst:
        if isinstance(x, dict):
            ids.append(x['id'])
        else:
            ids.append(x.id)
    if sort:
        ids = sorted(ids)
    return ids


############################################################
class BaseTests(TestCase):
    """
    General-purpose utility functions.
    """
    def setUp(self):
        self.username = 'test1'
        self.user = get_object_or_None(User, username=self.username)
        if not self.user:
            self.user = self.create_user(self.username)
        self.login(self.user)
        self.client = Client(enforce_csrf_checks=True)

    def tearDown(self):
        # we're caching the first session, which can screw things up (e.g. test_shortened_lsession)
        cache.clear()
        # from https://code.djangoproject.com/wiki/CookBookTestingTools
        #
        # explicit disconnect to destroy the in-memory db
        #
        # UPDATE: unnecessary - the problem turned out to be cacheing
        # from django.db import connection
        # connection.close()

    def login(self, user, password=None):
        if not password:
            password = user.username
        success = self.client.login(username=user.username, password=password)
        self.assertTrue(success)

    def refresh(self, x):
        """
        Returns X, having rerun a query to get the latest
        version.
        """
        return x.__class__.objects.get(pk=x.pk)


    def kwargs_ajax(self, kwargs):
        if kwargs.get('ajax', None):
            ajax = True
            # swap in the real arg
            del kwargs['ajax']
            kwargs['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
            # kwargs['content_type'] = 'text/javascript'
        else:
            ajax = False
        return kwargs, ajax


    def get(self, *args, **kwargs):
        """
        Light wrapper for client.get(). See self.post().

        Assumes you're expecting a STATUS_CODE of 200,
        unless you specify a different one, or None to avoid
        checking.
        """
        kwargs, ajax = self.kwargs_ajax(kwargs)
        resp = self.client.get(*args, **kwargs)
        # assume we're looking for STATUS_CODE of 200, unless specified otherwise
        status_code = kwargs.get('status_code', 200)
        if status_code is not None:
            self.assertEqual(resp.status_code, status_code)
        try:
            return resp, sjs.loads(resp.content) if ajax else None
        except:
            return resp, resp.content


    def get_aj(self, *args, **kwargs):
        kwargs['ajax'] = True
        resp, json = self.get(*args, **kwargs)
        return json


    def post(self, *args, **kwargs):
        """
        Light wrapper for client.post.

        Inputs:
          - AJAX: if True, sets HTTP_X_REQUESTED_WITH = 'XMLHttpRequest'

        Returns:
          - RESP: standard Django response
          - DCT: None, or a de-jsonified dictionary if ajax==True

        e.g.
          resp, d = self.post(url, dct, ajax=True)
        """
        kwargs, ajax = self.kwargs_ajax(kwargs)
        resp = self.client.post(*args, **kwargs)
        # assume we're looking for STATUS_CODE of 200, unless specified otherwise
        status_code = kwargs.get('status_code', 200)
        self.assertEqual(resp.status_code, status_code)
        return resp, sjs.loads(resp.content) if ajax and resp.content else None

    def disp_resp(self, resp, content=False):
        """
        You can't run RESP.KEYS(), so this lists the contents of a RESP
        """
        for field in dir(resp):
            if not content and field=='content': continue
            if field.startswith('_'): continue
            try:
                print '%s = %s\n\n' % (field,resp.__getattribute__(field))
            except (SyntaxError,KeyError):
                pass


    def create_user(self, username=None, date_joined=None, is_staff=False):
        if username is None:
            nUsers = User.objects.count()
            username = 'named%i' % nUsers
        kwargs = {'username': username,
                  'email': '%s@%s.com' % (username,username),
                  'password': username,}
        if date_joined:
            kwargs['date_joined'] = date_joined
        user = User.objects.create_user(**kwargs)
        if is_staff:
            user.is_staff = True
            user.save()
        return user


    def create_users(self, nUsers):
        for u in range(nUsers):
            user = self.create_user('user%i' % u)


    def assertEqualIds(self, ids1, ids2):
        return self.assertEqual(as_ids(ids1),
                                as_ids(ids2))

        

