# :set fileencoding=utf-8 :
import fakeredis
import json
import unittest
import uuid
from os import path
from flask.ext.testing import TestCase
from dorina import utils
from minimock import Mock, mock, restore, TraceTracker, assert_same_trace
import webdorina
import run

class RedisStore(object):
    def __init__(self, name, tracker=None):
        self.name = name
        self.tt = tracker
        self.connection = fakeredis.FakeRedis()

    def __getattr__(self, attr):
        def wrapped_call(*args, **kwargs):
            if self.tt is not None:
                name = "{0}.{1}".format(self.name, attr)
                self.tt.call(name, *args, **kwargs)
                return getattr(self.connection, attr)(*args, **kwargs)
        return wrapped_call


class RunTestCase(unittest.TestCase):
    def setUp(self):
        run.Redis = fakeredis.FakeRedis
        self.r = fakeredis.FakeStrictRedis()
        self.tt = TraceTracker()
        self.return_value = []
        mock('run.analyse', tracker=self.tt, returns_func=self.get_return_value)

    def tearDown(self):
        self.r.flushdb()
        restore()

    def get_return_value(self, *args, **kwargs):
        return self.return_value

    def test_run_analyse(self):
        '''Test run_analyze()'''
        expected_trace = '''Called run.analyse(
    datadir='/fake/data/dir',
    genome='hg19',
    match_a='any',
    region_a='any',
    set_a=['scifi'])'''

        query = dict(genome='hg19', set_a=['scifi'], match_a='any',
                     region_a='any')

        self.return_value = [
            {'data_source': 'scifi',
             'score': 5, 'track': 'chr1',
             'gene': 'gene01.01',
             'site': 'scifi_cds',
             'strand': '+',
             'location': 'chr1:250-260'
            },
            {'data_source': 'scifi',
             'score': 2, 'track': 'chr1',
             'gene': 'gene01.01',
             'site': 'scifi_cds',
             'strand': '+',
             'location': 'chr1:250-260'
             },
             {'data_source': 'scifi',
              'score': 7, 'track': 'chr1',
              'gene': 'gene01.02',
              'site': 'scifi_intron',
              'strand': '+',
              'location': 'chr1:2350-2360'}
        ]

        run.run_analyse('/fake/data/dir', 'results:fake_key', 'results:fake_key_pending', query, 'fake-uuid')
        self.return_value.sort(key=lambda x: x['score'], reverse=True)
        serialised_result = [ json.dumps(i) for i in self.return_value ]

        assert_same_trace(self.tt, expected_trace)

        self.assertTrue(self.r.exists('results:fake_key'))
        self.assertEqual(3, self.r.llen('results:fake_key'))
        self.assertEqual(serialised_result, self.r.lrange('results:fake_key', 0, -1))

        self.assertTrue(self.r.exists('sessions:fake-uuid'))
        self.assertEqual(json.loads(self.r.get('sessions:fake-uuid')), dict(uuid='fake-uuid', state='done'))

        self.assertTrue(self.r.exists('results:sessions:fake-uuid'))
        self.assertEqual(json.loads(self.r.get('results:sessions:fake-uuid')), dict(redirect="results:fake_key"))

    def test_run_analyse_no_results(self):
        '''Test run_analyze() when no results are returned'''
        query = dict(genome='hg19', set_a=['scifi'], match_a='any',
                     region_a='any')

        self.return_value = []

        run.run_analyse('/fake/data/dir', 'results:fake_key', 'results:fake_key_pending', query, 'fake-uuid')
        expected_result = [{
            'data_source': 'no results found',
            'score': -1,
            'track': '',
            'gene': '',
            'site': '',
            'strand': '',
            'location': ''
        }]

        serialised_result = [ json.dumps(i) for i in expected_result ]

        self.assertTrue(self.r.exists('results:fake_key'))
        self.assertEqual(1, self.r.llen('results:fake_key'))
        self.assertEqual(serialised_result, self.r.lrange('results:fake_key', 0, -1))

    def test_filter(self):
        '''Test filter()'''

        data = [
            {'data_source': 'scifi',
             'score': 5, 'track': 'chr1',
             'gene': 'gene01.01',
             'site': 'scifi_cds',
             'strand': '+',
             'location': 'chr1:250-260'
            },
            {'data_source': 'scifi',
             'score': 2, 'track': 'chr1',
             'gene': 'gene01.02',
             'site': 'scifi_cds',
             'strand': '+',
             'location': 'chr1:250-260'
             },
             {'data_source': 'scifi',
              'score': 7, 'track': 'chr1',
              'gene': 'gene01.03',
              'site': 'scifi_intron',
              'strand': '+',
              'location': 'chr1:2350-2360'}
        ]

        for d in data:
            self.r.rpush('results:fake_full_key', json.dumps(d))

        run.filter([u'gene01.01', 'gene01.02'], 'results:fake_full_key',
                   'results:fake_key', 'results:fake_key_pending', 'fake-uuid')

        data.pop()
        serialised_result = [ json.dumps(i) for i in data ]

        self.assertTrue(self.r.exists('results:fake_key'))
        self.assertEqual(2, self.r.llen('results:fake_key'))
        self.assertEqual(serialised_result, self.r.lrange('results:fake_key', 0, -1))

        self.assertTrue(self.r.exists('results:sessions:fake-uuid'))


class DorinaTestCase(TestCase):
    def create_app(self):
        self.app = webdorina.app
        return self.app

    def setUp(self):
        self.maxDiff = None
        self.tt = TraceTracker()
        webdorina.datadir = path.join(path.dirname(__file__), 'data')
        webdorina.redis_store = RedisStore('fake_store', self.tt)
        self.r = webdorina.redis_store.connection
        fake_queue = Mock('webdorina.Queue', tracker=self.tt)
        mock('webdorina.Queue', tracker=self.tt, returns=fake_queue)
        # use tracker=None to not track uuid4() calls
        mock('uuid.uuid4', tracker=None, returns="fake-uuid")

    def tearDown(self):
        self.r.flushdb()
        restore()

    def test_index(self):
        '''Test if index page displays'''
        rv = self.client.get('/')
        assert "doRiNA" in rv.data

    def test_list_regulators(self):
        '''Test list_regulators()'''
        expected = utils.get_regulators(datadir=webdorina.datadir)['h_sapiens']['hg19']
        rv = self.client.get('/regulators/hg19')
        self.assertDictEqual(rv.json, expected)
        rv = self.client.get('/regulators/at3')
        self.assertEqual(rv.json, dict())

    def test_search_nothing_cached(self):
        '''Test search() with nothing in cache'''
        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        key = 'results:{"combine": "or", "genes": ["all"], "genome": "hg19", '
        key += '"match_a": "any", "match_b": "any", "region_a": "any", '
        key += '"region_b": "any", "set_a": ["scifi"], "set_b": null}'
        key_pending = '{0}_pending'.format(key)

        rv = self.client.post('/search', data=data)

        # Now a query should be pending
        self.assertTrue(self.r.exists(key_pending))

        # A session should have been created as well
        self.assertTrue(self.r.exists('sessions:fake-uuid'))

        ttl = self.r.ttl(key_pending)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(uuid='fake-uuid', state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "pending", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {4})
Called fake_store.get(
    '{1}')
Called fake_store.set(
    '{1}',
    True)
Called fake_store.expire(
    '{1}',
    30)
Called webdorina.Queue(connection=<fakeredis.FakeRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    '{2}',
    '{0}',
    '{1}',
    {{{3}}},
    'fake-uuid')'''.format(key, key_pending, webdorina.datadir,
        "'genes': [u'all'], 'match_a': u'any', 'match_b': u'any', 'combine': u'or', 'genome': u'hg19', 'region_a': u'any', 'set_a': [u'scifi'], 'set_b': None, 'region_b': u'any'", webdorina.SESSION_TTL)
        assert_same_trace(self.tt, expected_trace)


    def test_search_query_pending(self):
        '''Test search() with a query for this key pending'''
        key = 'results:{"combine": "or", "genes": ["all"], "genome": "hg19", '
        key += '"match_a": "any", "match_b": "any", "region_a": "any", '
        key += '"region_b": "any", "set_a": ["scifi"], "set_b": null}'
        key_pending = '{0}_pending'.format(key)
        self.r.set(key_pending, True)

        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        # Should return "pending"
        self.assertEqual(rv.json, dict(uuid='fake-uuid', state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "pending", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {2})
Called fake_store.get(
    '{1}')'''.format(key, key_pending, webdorina.SESSION_TTL)
        assert_same_trace(self.tt, expected_trace)


    def test_search_cached_results(self):
        '''Test search() with cached_results'''
        key = 'results:{"combine": "or", "genes": ["all"], "genome": "hg19", '
        key += '"match_a": "any", "match_b": "any", "region_a": "any", '
        key += '"region_b": "any", "set_a": ["scifi"], "set_b": null}'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
            dict(track='fake', gene='fake02', data_source='fake source', score=23)
        ]
        for res in results:
            self.r.rpush(key, json.dumps(res))

        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        self.assertEqual(rv.json, dict(state='done', uuid="fake-uuid"))

        rv = self.client.get('/result/fake-uuid')
        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.expire(
    '{0}',
    {1})
Called fake_store.set(
    'sessions:{3}',
    '{{"state": "done", "uuid": "{3}"}}')
Called fake_store.expire('sessions:{3}', {4})
Called fake_store.set(
    'results:sessions:{3}',
    {5!r})
Called fake_store.expire('results:sessions:{3}', {4})
Called fake_store.exists('results:sessions:{3}')
Called fake_store.get('results:sessions:{3}')
Called fake_store.expire(
    '{0}',
    {1})
Called fake_store.lrange(
    '{0}',
    0,
    {2})
Called fake_store.llen(
    '{0}')
    '''.format(key, webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1,
               'fake-uuid', webdorina.SESSION_TTL, json.dumps(dict(redirect=key)))
        assert_same_trace(self.tt, expected_trace)


    def test_search_nothing_cached_all_regulators(self):
        '''Test search() for all regulators with nothing in cache'''
        data = dict(match_a='all', assembly='hg19')
        data['set_a[]']=['scifi', 'fake01']
        rv = self.client.post('/search', data=data)
        key = 'results:{"combine": "or", "genes": ["all"], "genome": "hg19", '
        key += '"match_a": "all", "match_b": "any", "region_a": "any", '
        key += '"region_b": "any", "set_a": ["scifi", "fake01"], "set_b": null}'
        key_pending = '{0}_pending'.format(key)

        # Now a query should be pending
        self.assertTrue(self.r.exists(key_pending))

        ttl = self.r.ttl(key_pending)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(uuid='fake-uuid', state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "pending", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {4})
Called fake_store.get(
    '{1}')
Called fake_store.set(
    '{1}',
    True)
Called fake_store.expire(
    '{1}',
    30)
Called webdorina.Queue(connection=<fakeredis.FakeRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    '{2}',
    '{0}',
    '{1}',
    {{{3}}},
    'fake-uuid')'''.format(key, key_pending, webdorina.datadir,
        "'genes': [u'all'], 'match_a': u'all', 'match_b': u'any', 'combine': u'or', 'genome': u'hg19', 'region_a': u'any', 'set_a': [u'scifi', u'fake01'], 'set_b': None, 'region_b': u'any'",
        webdorina.SESSION_TTL)
        assert_same_trace(self.tt, expected_trace)


    def test_search_nothing_cached_CDS_region(self):
        '''Test search() in CDS regions with nothing in cache'''
        data = dict(match_a='any', region_a='CDS', assembly='hg19')
        data['set_a[]']=['scifi', 'fake01']
        key = 'results:{"combine": "or", "genes": ["all"], "genome": "hg19", '
        key += '"match_a": "any", "match_b": "any", "region_a": "CDS", '
        key += '"region_b": "any", "set_a": ["scifi", "fake01"], "set_b": null}'
        key_pending = '{0}_pending'.format(key)

        rv = self.client.post('/search', data=data)

        # Now a query should be pending
        self.assertTrue(self.r.exists(key_pending))

        ttl = self.r.ttl(key_pending)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(uuid='fake-uuid', state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "pending", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {4})
Called fake_store.get(
    '{1}')
Called fake_store.set(
    '{1}',
    True)
Called fake_store.expire(
    '{1}',
    30)
Called webdorina.Queue(connection=<fakeredis.FakeRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    '{2}',
    '{0}',
    '{1}',
    {{{3}}},
    'fake-uuid')'''.format(key, key_pending, webdorina.datadir,
        "'genes': [u'all'], 'match_a': u'any', 'match_b': u'any', 'combine': u'or', 'genome': u'hg19', 'region_a': u'CDS', 'set_a': [u'scifi', u'fake01'], 'set_b': None, 'region_b': u'any'",
        webdorina.SESSION_TTL)
        assert_same_trace(self.tt, expected_trace)


    def test_search_filtered_results_cached(self):
        '''Test search() with filtered results in cache'''
        key = 'results:{"combine": "or", "genes": ["fake01"], "genome": "hg19", '
        key += '"match_a": "any", "match_b": "any", "region_a": "any", '
        key += '"region_b": "any", "set_a": ["scifi"], "set_b": null}'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
        ]
        for res in results:
            self.r.rpush(key, json.dumps(res))

        data = dict(match_a='any', assembly='hg19', genes='fake01')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        self.assertEqual(rv.json, dict(state='done', uuid="fake-uuid"))

        rv = self.client.get('/result/fake-uuid')
        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.expire(
    '{0}',
    {1})
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "done", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {3})
Called fake_store.set(
    'results:sessions:fake-uuid',
    {4!r})
Called fake_store.expire('results:sessions:fake-uuid', {3})
Called fake_store.exists('results:sessions:fake-uuid')
Called fake_store.get('results:sessions:fake-uuid')
Called fake_store.expire(
    '{0}',
    {1})
Called fake_store.lrange(
    '{0}',
    0,
    {2})
Called fake_store.llen(
    '{0}')
    '''.format(key, webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1,
               webdorina.SESSION_TTL, json.dumps(dict(redirect=key)))
        assert_same_trace(self.tt, expected_trace)


    def test_search_filtered_full_results_cached(self):
        '''Test search() with filter and full results in cache'''
        templ = 'results:{{"combine": "or", "genes": ["{0}"], "genome": "hg19", '
        templ += '"match_a": "any", "match_b": "any", "region_a": "any", '
        templ += '"region_b": "any", "set_a": ["scifi"], "set_b": null}}'
        full_key = templ.format('all')
        key = templ.format('fake01')
        key_pending = '{0}_pending'.format(key)
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
            dict(track='fake', gene='fake02', data_source='fake source', score=23)
        ]
        for res in results:
            self.r.rpush(full_key, json.dumps(res))


        data = dict(match_a='any', assembly='hg19', genes='fake01')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        # Now a query should be pending
        self.assertTrue(self.r.exists(key_pending))

        self.assertEqual(rv.json, dict(uuid='fake-uuid', state="pending"))

        # now pretend the filtering finished
        results.pop()
        self.r.set('results:sessions:fake-uuid', json.dumps(dict(redirect=key)))
        for res in results:
            self.r.rpush(key, json.dumps(res))

        rv = self.client.get('/result/fake-uuid')
        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    '{0}')
Called fake_store.exists(
    '{2}')
Called fake_store.expire(
    '{2}',
    {3})
Called fake_store.set(
    '{1}',
    True)
Called fake_store.expire(
    '{1}',
    30)
Called fake_store.set(
    'sessions:fake-uuid',
    '{{"state": "pending", "uuid": "fake-uuid"}}')
Called fake_store.expire('sessions:fake-uuid', {5})
Called webdorina.Queue(connection=<fakeredis.FakeRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function filter at ...>,
    [u'fake01'],
    '{2}',
    '{0}',
    '{1}',
    'fake-uuid')
Called fake_store.exists('results:sessions:fake-uuid')
Called fake_store.get('results:sessions:fake-uuid')
Called fake_store.expire(
    '{0}',
    {3})
Called fake_store.lrange(
    '{0}',
    0,
    {4})
Called fake_store.llen(
    '{0}')'''.format(key, key_pending, full_key, webdorina.RESULT_TTL,
                     webdorina.MAX_RESULTS - 1, webdorina.SESSION_TTL)
        assert_same_trace(self.tt, expected_trace)


    def test_status(self):
        '''Test status()'''
        got = self.client.get('/status/invalid')
        self.assertEqual(got.json, dict(uuid='invalid', state='expired'))

        valid = dict(uuid='valid', state='done')
        self.r.set('sessions:valid', json.dumps(valid))
        got = self.client.get('/status/valid')
        self.assertEqual(got.json, valid)
