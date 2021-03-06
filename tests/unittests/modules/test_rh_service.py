# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

import textwrap

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

import hubblestack.modules.rh_service as rh_service

RET = ['hostname', 'mountall', 'network-interface', 'network-manager',
       'salt-api', 'salt-master', 'salt-minion']


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RhServiceTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for hubblestack.modules.rh_service
    '''

    def setup_loader_modules(self):
        return {
            rh_service: {
                '_upstart_disable': None,
                '_upstart_enable': None,
                '_upstart_is_enabled': None
            }
        }

    @staticmethod
    def _m_lst():
        '''
        Return value for [].
        '''
        return MagicMock(return_value=[])

    @staticmethod
    def _m_ret():
        '''
        Return value for RET.
        '''
        return MagicMock(return_value=RET)

    @staticmethod
    def _m_bool(bol=True):
        '''
        Return Bool value.
        '''
        return MagicMock(return_value=bol)

    def test__chkconfig_is_enabled(self):
        '''
        test _chkconfig_is_enabled function
        '''
        name = 'atd'
        chkconfig_out = textwrap.dedent('''\

            {0}           0:off   1:off   2:off   3:on    4:on    5:on    6:off
            '''.format(name))
        xinetd_out = textwrap.dedent('''\
            xinetd based services:
                    {0}  on
            '''.format(name))

        with patch.object(rh_service, '_runlevel', MagicMock(return_value=3)):
            mock_run = MagicMock(return_value={'retcode': 0,
                                               'stdout': chkconfig_out})
            with patch.dict(rh_service.__mods__, {'cmd.run_all': mock_run}):
                self.assertTrue(rh_service._chkconfig_is_enabled(name))
                self.assertFalse(rh_service._chkconfig_is_enabled(name, 2))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 3))

            mock_run = MagicMock(return_value={'retcode': 0,
                                               'stdout': xinetd_out})
            with patch.dict(rh_service.__mods__, {'cmd.run_all': mock_run}):
                self.assertTrue(rh_service._chkconfig_is_enabled(name))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 2))
                self.assertTrue(rh_service._chkconfig_is_enabled(name, 3))

    def test_get_all(self):
        '''
        Test if it return all installed services. Use the ``limit``
        param to restrict results to services of that type.
        '''
        with patch.object(rh_service, '_upstart_services', self._m_ret()):
            self.assertListEqual(rh_service.get_all('upstart'), RET)

        with patch.object(rh_service, '_sysv_services', self._m_ret()):
            self.assertListEqual(rh_service.get_all('sysvinit'), RET)

            with patch.object(rh_service, '_upstart_services', self._m_lst()):
                self.assertListEqual(rh_service.get_all(), RET)

    def test_available(self):
        '''
        Test if it return True if the named service is available.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            self.assertTrue(rh_service.available('salt-api', 'upstart'))

        with patch.object(rh_service, '_service_is_sysv', self._m_bool()):
            self.assertTrue(rh_service.available('salt-api', 'sysvinit'))

            with patch.object(rh_service, '_service_is_upstart',
                              self._m_bool()):
                self.assertTrue(rh_service.available('salt-api'))

    def test_status(self):
        '''
        Test if it return the status for a service,
        returns a bool whether the service is running.
        '''
        with patch.object(rh_service, '_service_is_upstart', self._m_bool()):
            mock_run = MagicMock(return_value='start/running')
            with patch.dict(rh_service.__mods__, {'cmd.run': mock_run}):
                self.assertTrue(rh_service.status('salt-api'))

        with patch.object(rh_service, '_service_is_upstart',
                          self._m_bool(False)):
            with patch.dict(rh_service.__mods__, {'status.pid':
                                                  self._m_bool()}):
                self.assertTrue(rh_service.status('salt-api', sig=True))

            mock_ret = MagicMock(return_value=0)
            with patch.dict(rh_service.__mods__, {'cmd.retcode': mock_ret}):
                self.assertTrue(rh_service.status('salt-api'))

    def test_enabled(self):
        '''
        Test if it check to see if the named service is enabled
        to start on boot.
        '''
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.object(rh_service, '_service_is_upstart', mock_bool):
            with patch.object(rh_service, '_upstart_is_enabled', MagicMock(return_value=False)):
                self.assertFalse(rh_service.enabled('salt-api'))

            with patch.object(rh_service, '_sysv_is_enabled', self._m_bool()):
                self.assertTrue(rh_service.enabled('salt-api'))
