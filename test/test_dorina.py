# :set fileencoding=utf-8 :
import fakeredis
import json
import unittest
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
        self.connection = fakeredis.FakeStrictRedis()

    def __getattr__(self, attr):
        def wrapped_call(*args, **kwargs):
            if self.tt is not None:
                name = "{0}.{1}".format(self.name, attr)
                self.tt.call(name, *args, **kwargs)
                return getattr(self.connection, attr)(*args, **kwargs)
        return wrapped_call


class RunTestCase(unittest.TestCase):
    def setUp(self):
        run.Redis = fakeredis.FakeStrictRedis
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

        run.run_analyse('/fake/data/dir', 'results:fake_key', 'results:fake_key_pending', query)
        self.return_value.sort(key=lambda x: x['score'], reverse=True)
        serialised_result = [ json.dumps(i) for i in self.return_value ]

        assert_same_trace(self.tt, expected_trace)

        self.assertTrue(self.r.exists('results:fake_key'))
        self.assertEqual(3, self.r.llen('results:fake_key'))
        self.assertEqual(serialised_result, self.r.lrange('results:fake_key', 0, -1))

    def test_run_analyse_no_results(self):
        '''Test run_analyze() when no results are returned'''
        query = dict(genome='hg19', set_a=['scifi'], match_a='any',
                     region_a='any')

        self.return_value = []

        run.run_analyse('/fake/data/dir', 'results:fake_key', 'results:fake_key_pending', query)
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

        run.filter([u'gene01.01', 'gene01.02'], 'results:fake_full_key', 'results:fake_key', 'results:fake_key_pending')

        data.pop()
        serialised_result = [ json.dumps(i) for i in data ]

        self.assertTrue(self.r.exists('results:fake_key'))
        self.assertEqual(2, self.r.llen('results:fake_key'))
        self.assertEqual(serialised_result, self.r.lrange('results:fake_key', 0, -1))


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

    def tearDown(self):
        self.r.flushdb()
        restore()

    def test_index(self):
        '''Test if index page displays'''
        rv = self.client.get('/')
        assert "doRiNA" in rv.data

    def test_list_clades(self):
        '''Test list_clades()'''
        rv = self.client.get('/clades')
        self.assertEqual(rv.json, dict(clades=['mammals', 'nematodes']))

    def test_list_genomes(self):
        '''Test list_genomes()'''
        rv = self.client.get('/genomes/nematodes')
        self.assertEqual(rv.json, dict(clade='nematodes', genomes=['c_elegans']))
        rv = self.client.get('/genomes/mammals')
        self.assertEqual(rv.json, dict(clade='mammals', genomes=['h_sapiens', 'm_musculus']))
        rv = self.client.get('/genomes/plants')
        self.assertEqual(rv.json, dict(clade=''))

    def test_list_assemblies(self):
        '''Test list_assemblies()'''
        rv = self.client.get('/assemblies/nematodes/c_elegans')
        self.assertEqual(rv.json, dict(clade='nematodes', genome='c_elegans', assemblies=['ce6']))
        rv = self.client.get('/assemblies/mammals/h_sapiens')
        self.assertEqual(rv.json, dict(clade='mammals', genome='h_sapiens', assemblies=['hg19']))
        rv = self.client.get('/assemblies/plants/a_thaliana')
        self.assertEqual(rv.json, dict(clade=''))
        rv = self.client.get('/assemblies/mammals/r_norvegicus')
        self.assertEqual(rv.json, dict(clade='mammals', genome=''))

    def test_list_regulators(self):
        '''Test list_regulators()'''
        expected = utils.get_regulators(datadir=webdorina.datadir)['mammals']['h_sapiens']['hg19']
        rv = self.client.get('/regulators/mammals/h_sapiens/hg19')
        self.assertDictEqual(rv.json, expected)
        rv = self.client.get('/regulators/plants/a_thaliana/at3')
        self.assertEqual(rv.json, dict(clade=''))
        rv = self.client.get('/regulators/mammals/r_norvegicus/rn3')
        self.assertEqual(rv.json, dict(clade='mammals', genome=''))
        rv = self.client.get('/regulators/mammals/h_sapiens/hg17')
        self.assertEqual(rv.json, dict(clade='mammals', genome='h_sapiens', assembly=''))

    def test_search_nothing_cached(self):
        '''Test search() with nothing in cache'''
        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending'

        # Now a query should be pending
        self.assertTrue(self.r.exists(key))

        ttl = self.r.ttl(key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending')
Called fake_store.set(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending',
    True)
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending',
    30)
Called webdorina.Queue(
    connection=<fakeredis.FakeStrictRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    %r,
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending',
    {'region_a': u'any', 'set_a': [u'scifi'], 'genes': [u'all'], 'match_a': u'any', 'genome': u'hg19'})''' % webdorina.datadir
        assert_same_trace(self.tt, expected_trace)


    def test_search_query_pending(self):
        '''Test search() with a query for this key pending'''
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending'
        self.r.set(key, True)

        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        # Should return "pending"
        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending')'''
        assert_same_trace(self.tt, expected_trace)


    def test_search_cached_results(self):
        '''Test search() with cached_results'''
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
            dict(track='fake', gene='fake02', data_source='fake source', score=23)
        ]
        for res in results:
            self.r.rpush(key, json.dumps(res))

        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        rv = self.client.post('/search', data=data)

        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    %s)
Called fake_store.lrange(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    0,
    %s)
Called fake_store.llen(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
    ''' % (webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1)
        assert_same_trace(self.tt, expected_trace)


    def test_search_nothing_cached_all_regulators(self):
        '''Test search() for all regulators with nothing in cache'''
        data = dict(match_a='all', assembly='hg19')
        data['set_a[]']=['scifi', 'fake01']
        rv = self.client.post('/search', data=data)
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}_pending'

        # Now a query should be pending
        self.assertTrue(self.r.exists(key))

        ttl = self.r.ttl(key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}_pending')
Called fake_store.set(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}_pending',
    True)
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}_pending',
    30)
Called webdorina.Queue(
    connection=<fakeredis.FakeStrictRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    %r,
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}',
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "all", "region_a": "any", "set_a": ["scifi", "fake01"]}_pending',
    {'region_a': u'any', 'set_a': [u'scifi', u'fake01'], 'genes': [u'all'], 'match_a': u'all', 'genome': u'hg19'})''' % webdorina.datadir
        assert_same_trace(self.tt, expected_trace)


    def test_search_nothing_cached_CDS_region(self):
        '''Test search() in CDS regions with nothing in cache'''
        data = dict(match_a='any', region_a='CDS', assembly='hg19')
        data['set_a[]']=['scifi', 'fake01']
        rv = self.client.post('/search', data=data)
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}_pending'

        # Now a query should be pending
        self.assertTrue(self.r.exists(key))

        ttl = self.r.ttl(key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}_pending')
Called fake_store.set(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}_pending',
    True)
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}_pending',
    30)
Called webdorina.Queue(
    connection=<fakeredis.FakeStrictRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    %r,
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}',
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "CDS", "set_a": ["scifi", "fake01"]}_pending',
    {'region_a': u'CDS', 'set_a': [u'scifi', u'fake01'], 'genes': [u'all'], 'match_a': u'any', 'genome': u'hg19'})''' % webdorina.datadir
        assert_same_trace(self.tt, expected_trace)


    def test_search_filtered_results_cached(self):
        '''Test search() with filtered results in cache'''
        key = 'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
        ]
        for res in results:
            self.r.rpush(key, json.dumps(res))

        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        data['genes[]']=['fake01']
        rv = self.client.post('/search', data=data)

        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.expire(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    %s)
Called fake_store.lrange(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    0,
    %s)
Called fake_store.llen(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
    ''' % (webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1)
        assert_same_trace(self.tt, expected_trace)


    def test_search_filtered_full_results_cached(self):
        '''Test search() with filter and full results in cache'''
        full_key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}'
        key = 'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}'
        key_pending = 'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
            dict(track='fake', gene='fake02', data_source='fake source', score=23)
        ]
        for res in results:
            self.r.rpush(full_key, json.dumps(res))


        data = dict(match_a='any', assembly='hg19')
        data['set_a[]']=['scifi']
        data['genes[]']=['fake01']
        rv = self.client.post('/search', data=data)

        # Now a query should be pending
        self.assertTrue(self.r.exists(key_pending))

        self.assertEqual(rv.json, dict(state="pending"))

        # now pretend the filtering finished
        results.pop()
        for res in results:
            self.r.rpush(key, json.dumps(res))

        rv = self.client.post('/search', data=data)
        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    %s)
Called fake_store.set(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending',
    True)
Called fake_store.expire(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending',
    30)
Called webdorina.Queue(
    connection=<fakeredis.FakeStrictRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function filter at ...>,
    [u'fake01'],
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}_pending')
Called fake_store.exists(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
Called fake_store.expire(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    %s)
Called fake_store.lrange(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}',
    0,
    %s)
Called fake_store.llen(
    'results:{"genes": ["fake01"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": ["scifi"]}')
    ''' % (webdorina.RESULT_TTL, webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1)
        assert_same_trace(self.tt, expected_trace)
