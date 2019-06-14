import unittest

from influxdb.client import InfluxDBClientError

from munininfluxdb.influxdbclient import InfluxdbClient

from . import mock


@unittest.skipUnless(mock, "unittest.mock is not available.")
class TestInfluxDBClient(unittest.TestCase):

    def setUp(self):
        self.patcher = mock.patch('munininfluxdb.influxdbclient.influxdb')
        self.__influxdb = self.patcher.start()
        self.mock_settings = mock.MagicMock()
        self.mock_settings.influxdb = {
            'database': 'foo',
            'host': 'host',
            'port': 123,
            'user': 'user',
            'password': 'password',
        }
        self.mock_settings.interactive = False

    def tearDown(self):
        self.patcher.stop()

    def test_connect(self):
        client = InfluxdbClient(self.mock_settings)
        result = client.connect()
        self.__influxdb.assert_has_calls([
            mock.call.InfluxDBClient('host', 123, 'user', 'password'),
            mock.call.InfluxDBClient().get_list_database(),
            mock.call.InfluxDBClient().switch_database('foo'),
        ])
        self.assertIsNotNone(client.client)
        self.assertTrue(result)

    def test_connect_default_db(self):
        '''
        If the "database" setting in the settings is empty, use the default DB.
        '''
        self.mock_settings.influxdb['database'] = ''
        client = InfluxdbClient(self.mock_settings)
        result = client.connect()
        self.__influxdb.assert_has_calls([
            mock.call.InfluxDBClient('host', 123, 'user', 'password'),
            mock.call.InfluxDBClient().get_list_database(),
        ])
        self.assertIsNotNone(client.client)
        self.assertTrue(result)

    def test_test_db_existing(self):
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.get_list_database().__contains__.return_value = True
        client.test_db('bla')
        client.client.assert_has_calls([
            mock.call.switch_database('bla'),
        ])

    def test_test_db_nonexisting(self):
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.get_list_database().__contains__.return_value = False
        client.test_db('bla')
        client.client.assert_has_calls([
            mock.call.create_database('bla'),
            mock.call.switch_database('bla'),
        ])

    def test_test_db_error_on_create(self):
        from influxdb.client import InfluxDBClientError as IE
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.create_database.side_effect = IE('foo')
        result = client.test_db('bla')
        self.assertFalse(result)

    def test_test_db_error_on_switch(self):
        from influxdb.client import InfluxDBClientError as IE
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.switch_database.side_effect = IE('foo')
        result = client.test_db('bla')
        self.assertFalse(result)

    def test_test_db_error_on_query(self):
        from influxdb.client import InfluxDBClientError as IE
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.query.side_effect = IE('foo')
        result = client.test_db('bla')
        self.assertFalse(result)

    def test_list_db(self):
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.get_list_database.return_value = [
            {'name': 'db1'},
            {'name': 'db2'},
        ]
        with mock.patch('munininfluxdb.influxdbclient.print') as p:
            result = client.list_db()
        self.assertEqual(len(p.mock_calls), 3)
        self.assertIsNone(result)

    def test_list_series(self):
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        token = object()
        client.client.get_list_series.return_value = token
        result = client.list_series()
        self.assertEqual(result, token)
        client.client.get_list_series.assert_called_with()

    def test_list_columns(self):
        client = InfluxdbClient(self.mock_settings)
        client.connect()
        client.client.query.return_value = [{
            'a': 1,
            'points': 123,
            'columns': ['foo', 'time', 'sequence_number']
        }]

        expected = [{
            'a': 1,
            'columns': ['foo']
        }]
        result = client.list_columns()
        client.client.query.assert_called_with('SELECT * FROM "/.*/" LIMIT 1')
        self.assertEqual(result, expected)

    @mock.patch('munininfluxdb.influxdbclient.prompt')
    @mock.patch('munininfluxdb.influxdbclient.ask_password')
    def test_prompt_setup(self, m_askpw, m_prompt):
        # --- Prepare & Prime mocks
        self.mock_settings.influxdb = {
            'host': 'settings-hostname'
        }
        client = InfluxdbClient(self.mock_settings)
        m_askpw.return_value = 'supersecret'
        m_prompt.side_effect = [
            'the-hostname',
            'the-port',
            'the-user',
            'the-database',
            'the-database',
            'group-field-value',
        ]
        new_settings = {
            'hello': 'world'
        }
        client.test_db = mock.MagicMock()
        client.test_db.side_effect = [False, True]
        client.connect = mock.MagicMock()

        def dummy_connect(*args, **kwargs):
            """
            Connect is called 4 times with the setup done in this test. The
            first call returns ``False`` triggering user prompts. These prompts
            have been primed above using the ``m_prompt`` side effects, so we
            know what should come out of it.
            """
            self.mock_settings.influxdb.update(new_settings)
            yield False
            yield True
            yield True
            yield True

        client.connect.side_effect = dummy_connect()

        # --- Make the call that should be tested
        client.prompt_setup()

        # --- Run Assertions
        m_prompt.assert_has_calls([
            mock.call('HOST_HANDLE', 'settings-hostname'),
            mock.call('PORT', 8086),
            mock.call('USER', None),
            mock.call('HOST_HANDLE', 'the-hostname'),
            mock.call('DATABASE', 'munin'),
            mock.call('GROUP_FIELDS', 'y'),
        ])
        self.fail('TODO')  # XXX

    def test_write_series(self):
        # TODO The exceptions in this function are not yet tested.
        client = InfluxdbClient(self.mock_settings)
        client.connect()

        measurement = 'measurement'
        tags = ['tag1', 'tag2']
        fields = ['field1', 'column1', 'column2']
        timeval1 = 'the-time-value'
        timeval2 = 'col-1-value'
        timeval3 = 'col-2-value'
        time_and_values = [
            [timeval1, timeval2, timeval3]
        ]

        expected_payload = {
            'fields': {'column1': 'col-1-value', 'column2': 'col-2-value'},
            'tags': ['tag1', 'tag2'],
            'time': 'the-time-value',
            'measurement': 'measurement'
        }
        result = client.write_series(
            measurement, tags, fields, time_and_values)

        client.client.write_points.assert_called_with(
            [expected_payload], time_precision='s')
        self.assertIsNone(result)

    def test_validate_record(self):
        # TODO The exceptions in this function are not yet tested.
        client = InfluxdbClient(self.mock_settings)
        client.connect()

        # Query is called multiple times, using side_effect to define
        # return_values for each call.
        client.client.query.side_effect = [
            ['a', 'b', 'c'],  # SHOW MEASUREMENT query
            [10],  # COUNT('field1')
            [20],  # COUNT('field2')
        ]

        client.validate_record('the-name', ['field1', 'field2'])

        client.client.query.assert_has_calls([
            mock.call('SHOW MEASUREMENTS WITH MEASUREMENT="the-name"'),
            mock.call('SELECT COUNT("field1") FROM "the-name"'),
            mock.call('SELECT COUNT("field2") FROM "the-name"'),
        ])

    def test_import_from_xml(self):
        # --- Prepare the "settings" for this test ------
        self.mock_settings.influxdb['group_fields'] = 'a'
        self.mock_settings.iter_plugins.return_value = [
            ('a', 'b', 'c'),
            ('d', 'e', 'f'),
        ]
        plugin_c = mock.MagicMock(
            name='plugin_c',
            fields={'field_ca': mock.MagicMock(rrd_exported=True)}
        )
        plugin_f = mock.MagicMock(
            name='plugin_f',
            fields={'field_fa': mock.MagicMock(rrd_exported=True)}
        )
        self.mock_settings.domains = {
            'a': mock.MagicMock(
                hosts={
                    'b': mock.MagicMock(
                        plugins={'c': plugin_c}
                    )
                }
            ),
            'd': mock.MagicMock(
                hosts={
                    'e': mock.MagicMock(
                        plugins={'f': plugin_f}
                    )
                }
            ),
        }

        # --- Create the testing instance. ---------
        client = InfluxdbClient(self.mock_settings)
        client.connect()

        # --- Mocking -----------
        # We'll mock out "write_series". It's tested in another test.
        #
        # ProgressBar and read_xml_file are externals and we don't want to
        # execute them.
        #
        # We'll also mock out "print". This will remove stdout during testing.
        # If we wanted, we could assign the patch result to a variable and check
        # the calls. We don't do this as it's end-user "display" stuff and not
        # relevant to the underlying logic.
        with mock.patch('munininfluxdb.influxdbclient.print'), \
                mock.patch('munininfluxdb.influxdbclient.read_xml_file') as rxml, \
                mock.patch('munininfluxdb.influxdbclient.ProgressBar'), \
                mock.patch('munininfluxdb.influxdbclient.InfluxdbClient.write_series') as ptch:

            rxml.return_value = mock.MagicMock()
            rxml().items.return_value = [('key', 'value')]
            client.import_from_xml()

        ptch.assert_has_calls([
            mock.call(
                'c',
                {
                    'domain': 'a',
                    'is_multigraph': True,
                    'host': 'b',
                    'plugin': 'c'
                },
                ['time', 'field_ca'],
                [['key', 'value']]),
            mock.call(
                'f',
                {
                    'domain': 'd',
                    'is_multigraph': True,
                    'host': 'e',
                    'plugin': 'f'
                },
                ['time', 'field_fa'],
                [['key', 'value']])
        ])

    def test_import_from_xml_folder(self):
        self.skipTest('Deprecated')
