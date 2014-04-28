# :set fileencoding=utf-8 :
import fakeredis
import json
from os import path
from flask.ext.testing import TestCase
from dorina import utils
from minimock import Mock, mock, restore, TraceTracker, assert_same_trace
import webdorina

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
        data = dict(match_a='any', assembly='hg19', set_a=['scifi'])
        rv = self.client.post('/search', data=data)
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending'

        # Now a query should be pending
        self.assertTrue(self.r.exists(key))

        ttl = self.r.ttl(key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, webdorina.RESULT_TTL)

        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending')
Called fake_store.set(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending',
    True)
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending',
    30)
Called webdorina.Queue(
    connection=<fakeredis.FakeStrictRedis object at ...>)
Called webdorina.Queue.enqueue(
    <function run_analyse at ...>,
    %r,
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}',
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending',
    {'region_a': u'any', 'set_a': [], 'genes': [u'all'], 'match_a': u'any', 'genome': u'hg19'})''' % webdorina.datadir
        assert_same_trace(self.tt, expected_trace)


    def test_search_query_pending(self):
        '''Test search() with a query for this key pending'''
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending'
        self.r.set(key, True)

        data = dict(match_a='any', assembly='hg19', set_a=['scifi'])
        rv = self.client.post('/search', data=data)

        # Should return "pending"
        self.assertEqual(rv.json, dict(state="pending"))

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}')
Called fake_store.get(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}_pending')'''
        assert_same_trace(self.tt, expected_trace)


    def test_search_cached_results(self):
        '''Test search() with cached_results'''
        key = 'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}'
        results = [
            dict(track='fake', gene='fake01', data_source='fake source', score=42),
            dict(track='fake', gene='fake02', data_source='fake source', score=23)
        ]
        for res in results:
            self.r.rpush(key, json.dumps(res))

        data = dict(match_a='any', assembly='hg19', set_a=['scifi'])
        rv = self.client.post('/search', data=data)

        # Should return "pending"
        expected = dict(state='done', results=results, more_results=False, next_offset=100)
        self.assertEqual(rv.json, expected)

        # This query should trigger a defined set of calls
        expected_trace = '''Called fake_store.exists(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}')
Called fake_store.expire(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}',
    %s)
Called fake_store.lrange(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}',
    0,
    %s)
Called fake_store.llen(
    'results:{"genes": ["all"], "genome": "hg19", "match_a": "any", "region_a": "any", "set_a": []}')
    ''' % (webdorina.RESULT_TTL, webdorina.MAX_RESULTS - 1)
        assert_same_trace(self.tt, expected_trace)
