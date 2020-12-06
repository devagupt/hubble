# -*- coding: utf-8 -*-
'''
Tests for hubblestack.utils.path
'''

import os
import sys
import posixpath
import ntpath
import platform
import tempfile

from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

import importlib
import hubblestack.utils.path
import hubblestack.utils.platform
from hubblestack.exceptions import CommandNotFoundError


class PathJoinTestCase(TestCase):

    PLATFORM_FUNC = platform.system
    BUILTIN_MODULES = sys.builtin_module_names

    NIX_PATHS = (
        (('/', 'key'), '/key'),
        (('/etc/salt', '/etc/salt/pki'), '/etc/salt/etc/salt/pki'),
        (('/usr/local', '/etc/salt/pki'), '/usr/local/etc/salt/pki')

    )

    WIN_PATHS = (
        (('c:', 'temp', 'foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        ((r'c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo', 'bar'), 'c:\\temp\\foo\\bar'),
        (('c:', r'\temp', r'\foo\bar'), 'c:\\temp\\foo\\bar'),
    )

    def test_nix_paths(self):
        if platform.system().lower() == "windows":
            self.skipTest(
                "Windows platform found. not running *nix hubblestack.utils.path.join tests"
            )
        for idx, (parts, expected) in enumerate(self.NIX_PATHS):
            path = hubblestack.utils.path.join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    def test_windows_paths(self):
        if platform.system().lower() != "windows":
            self.skipTest(
                'Non windows platform found. not running non patched os.path '
                'hubblestack.utils.path.join tests'
            )

        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = hubblestack.utils.path.join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    @skipIf(hubblestack.utils.platform.is_windows(), '*nix-only test')
    def test_mixed_unicode_and_binary(self):
        '''
        This tests joining paths that contain a mix of components with unicode
        strings and non-unicode strings with the unicode characters as binary.

        This is no longer something we need to concern ourselves with in
        Python 3, but the test should nonetheless pass on Python 3. Really what
        we're testing here is that we don't get a UnicodeDecodeError when
        running on Python 2.
        '''
        a = u'/foo/bar'
        b = 'Д'
        expected = u'/foo/bar/\u0414'
        actual = hubblestack.utils.path.join(a, b)
        self.assertEqual(actual, expected)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PathTestCase(TestCase):
    def test_which_bin(self):
        ret = hubblestack.utils.path.which_bin('str')
        self.assertIs(None, ret)

        test_exes = ['ls', 'echo']
        with patch('hubblestack.utils.path.which', return_value='/tmp/dummy_path'):
            ret = hubblestack.utils.path.which_bin(test_exes)
            self.assertEqual(ret, '/tmp/dummy_path')

            ret = hubblestack.utils.path.which_bin([])
            self.assertIs(None, ret)

        with patch('hubblestack.utils.path.which', return_value=''):
            ret = hubblestack.utils.path.which_bin(test_exes)
            self.assertIs(None, ret)

    def test_sanitize_win_path(self):
        p = '\\windows\\system'
        self.assertEqual(hubblestack.utils.path.sanitize_win_path('\\windows\\system'), '\\windows\\system')
        self.assertEqual(hubblestack.utils.path.sanitize_win_path('\\bo:g|us\\p?at*h>'), '\\bo_g_us\\p_at_h_')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_check_or_die(self):
        self.assertRaises(CommandNotFoundError, hubblestack.utils.path.check_or_die, None)

        with patch('hubblestack.utils.path.which', return_value=False):
            self.assertRaises(CommandNotFoundError, hubblestack.utils.path.check_or_die, 'FAKE COMMAND')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_join(self):
        with patch('hubblestack.utils.platform.is_windows', return_value=False) as is_windows_mock:
            self.assertFalse(is_windows_mock.return_value)
            expected_path = os.path.join(os.sep + 'a', 'b', 'c', 'd')
            ret = hubblestack.utils.path.join('/a/b/c', 'd')
            self.assertEqual(ret, expected_path)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestWhich(TestCase):
    '''
    Tests hubblestack.utils.path.which function to ensure that it returns True as
    expected.
    '''

    # The mock patch below will make sure that ALL calls to the which function
    # returns None
    def test_missing_binary_in_linux(self):
        with patch('hubblestack.utils.path.which', lambda exe: None):
            self.assertTrue(
                hubblestack.utils.path.which('this-binary-does-not-exist') is None
            )

    # The mock patch below will make sure that ALL calls to the which function
    # return whatever is sent to it
    def test_existing_binary_in_linux(self):
        with patch('hubblestack.utils.path.which', lambda exe: exe):
            self.assertTrue(hubblestack.utils.path.which('this-binary-exists-under-linux'))

    def test_existing_binary_in_windows(self):
        with patch('os.access') as osaccess:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.access
            # returns X, the second Y, the third Z, etc...
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                False,
                # We will now also return False once so we get a .EXE back from
                # the function, see PATHEXT below.
                False,
                # Lastly return True, this is the windows check.
                True
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin',
                                         'PATHEXT': '.COM;.EXE;.BAT;.CMD'}):
                # Let's also patch is_windows to return True
                with patch('hubblestack.utils.platform.is_windows', lambda: True):
                    with patch('os.path.isfile', lambda x: True):
                        self.assertEqual(
                            hubblestack.utils.path.which('this-binary-exists-under-windows'),
                            os.path.join(os.sep + 'bin', 'this-binary-exists-under-windows.EXE')
                        )

    def test_missing_binary_in_windows(self):
        with patch('os.access') as osaccess:
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                # which() will add 4 extra paths to the given one, os.access will
                # be called 5 times
                False, False, False, False, False
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin'}):
                # Let's also patch is_widows to return True
                with patch('hubblestack.utils.platform.is_windows', lambda: True):
                    self.assertEqual(
                        # Since we're passing the .exe suffix, the last True above
                        # will not matter. The result will be None
                        hubblestack.utils.path.which('this-binary-is-missing-in-windows.exe'),
                        None
                    )

    def test_existing_binary_in_windows_pathext(self):
        with patch('os.access') as osaccess:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.access
            # returns X, the second Y, the third Z, etc...
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                False,
                # We will now also return False 3 times so we get a .CMD back from
                # the function, see PATHEXT below.
                # Lastly return True, this is the windows check.
                False, False, False,
                True
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin',
                                         'PATHEXT': '.COM;.EXE;.BAT;.CMD;.VBS;'
                                         '.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.PY'}):
                # Let's also patch is_windows to return True
                with patch('hubblestack.utils.platform.is_windows', lambda: True):
                    with patch('os.path.isfile', lambda x: True):
                        self.assertEqual(
                            hubblestack.utils.path.which('this-binary-exists-under-windows'),
                            os.path.join(os.sep + 'bin', 'this-binary-exists-under-windows.CMD')
                        )