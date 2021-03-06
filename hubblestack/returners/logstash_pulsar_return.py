# -*- encoding: utf-8 -*-
"""
HubbleStack Pulsar-to-Logstash (http input) returner

Deliver HubbleStack Pulsar event data into Logstash using the HTTP input
plugin. Required config/pillar settings:

.. code-block:: yaml

    hubblestack:
      returner:
        logstash:
          - port: 8080
            proxy: {}
            timeout: 10
            user: username
            indexer_ssl: True
            sourcetype_pulsar: hubble_fim
            indexer: http://logstash.http.input.tld
            password: password
            custom_fields:
              - site
              - product_group
"""
from collections import defaultdict

import os
import json
import requests
from requests.auth import HTTPBasicAuth


def _dedup_list(input_list):
    """
    Remove duplicates from a list
    """
    deduped = []
    for idx, item in enumerate(input_list):
        if item not in input_list[idx + 1:]:
            deduped.append(item)
    return deduped


def returner(ret):
    """
    Gather data for pulsar and post it to logstash according to the config
    """
    if isinstance(ret, dict) and not ret.get('return'):
        return

    opts_list = _get_options()
    data = _dedup_list(ret['return'])
    fqdn = __grains__['fqdn'] if __grains__['fqdn'] else __opts__['id']
    try:
        fqdn_ip4 = __grains__['fqdn_ip4'][0]
    except IndexError:
        fqdn_ip4 = __grains__['ipv4'][0]
    if fqdn_ip4.startswith('127.'):
        for ip4_addr in __grains__['ipv4']:
            if ip4_addr and not ip4_addr.startswith('127.'):
                fqdn_ip4 = ip4_addr
                break
    # Get cloud details
    cloud_details = __grains__.get('cloud_details', {})

    for opts in opts_list:
        # get the alerts
        alerts = _build_alerts(data)
        for alert in alerts:
            if 'change' in alert:  # Linux, normal pulsar
                # The second half of the change will be '|IN_ISDIR' for directories
                change = alert['change'].split('|')[0]
                # Skip the IN_IGNORED events
                if change == 'IN_IGNORED':
                    continue
                event = _build_linux_event(alert=alert, change=change)
            else:  # Windows, win_pulsar
                change = alert['Accesses']
                event = _build_windows_event(alert=alert, change=change)
                # TODO: Should we be reporting 'EntryType' or 'TimeGenerated?
                #   EntryType reports whether attempt to change was successful.
            event.update({'minion_id': __opts__['id'],
                          'dest_host': fqdn,
                          'dest_ip': fqdn_ip4})
            event.update(cloud_details)

            payload = {'host': fqdn,
                       'index': opts['index'],
                       'sourcetype': opts['sourcetype'],
                       'event': event}

            rdy = json.dumps(payload)
            requests.post('{}:{}/hubble/pulsar'.format(opts['indexer'], opts['port']), rdy,
                          auth=HTTPBasicAuth(opts['user'], opts['password']))
    return


def _get_options():
    """
    Function that aggregates the configs for logstasg and returns them as a list of dicts.
    """
    if __mods__['config.get']('hubblestack:returner:logstash'):
        returner_opts = __mods__['config.get']('hubblestack:returner:logstash')
        if not isinstance(returner_opts, list):
            returner_opts = [returner_opts]
        return [_process_opt(opt) for opt in returner_opts]
    try:
        logstash_opts = {
            'password': __mods__['config.get']('hubblestack:returner:logstash:password'),
            'indexer': __mods__['config.get']('hubblestack:returner:logstash:indexer'),
            'sourcetype': __mods__['config.get']('hubblestack:pulsar:returner:logstash:sourcetype'),
            'port': __mods__['config.get']('hubblestack:returner:logstash:port'),
            'user': __mods__['config.get']('hubblestack:returner:logstash:user'),
            'custom_fields': __mods__['config.get'](
                'hubblestack:pulsar:returner:logstash:custom_fields', []),
            'http_input_server_ssl': __mods__['config.get'](
                'hubblestack:pulsar:returner:logstash:indexer_ssl', True),
            'proxy': __mods__['config.get']('hubblestack:pulsar:returner:logstash:proxy', {}),
            'timeout': __mods__['config.get']('hubblestack:pulsar:returner:logstash:timeout', 9.05)}
    except Exception:
        return None

    return [logstash_opts]


def _process_opt(opt):
    """
    Helper function that extracts certain fields from the opt dict and assembles the processed dict
    """
    return {'password': opt.get('password'),
            'user': opt.get('user'),
            'indexer': opt.get('indexer'),
            'port': str(opt.get('port', '8080')),
            'index': opt.get('index'),
            'custom_fields': opt.get('custom_fields', []),
            'sourcetype': opt.get('sourcetype_pulsar', 'hubble_fim'),
            'indexer_ssl': opt.get('indexer_ssl', True),
            'proxy': opt.get('proxy', {}),
            'timeout': opt.get('timeout', 9.05)}


def _build_linux_actions():
    """
    Helper function that builds the actions defaultdict for Linux - pulsar
    """
    actions = defaultdict(lambda: 'unknown')
    actions['IN_ACCESS'] = 'read'
    actions['IN_ATTRIB'] = 'acl_modified'
    actions['IN_CLOSE_NOWRITE'] = 'read'
    actions['IN_CLOSE_WRITE'] = 'read'
    actions['IN_CREATE'] = 'created'
    actions['IN_DELETE'] = 'deleted'
    actions['IN_DELETE_SELF'] = 'deleted'
    actions['IN_MODIFY'] = 'modified'
    actions['IN_MOVE_SELF'] = 'modified'
    actions['IN_MOVED_FROM'] = 'modified'
    actions['IN_MOVED_TO'] = 'modified'
    actions['IN_OPEN'] = 'read'
    actions['IN_MOVE'] = 'modified'
    actions['IN_CLOSE'] = 'read'

    return actions


def _build_windows_actions():
    """
    Helper function that builds the actions defaultdict for Windows - win_pulsar
    """
    actions = defaultdict(lambda: 'unknown')
    actions['Delete'] = 'deleted'
    actions['Read Control'] = 'read'
    actions['Write DAC'] = 'acl_modified'
    actions['Write Owner'] = 'modified'
    actions['Synchronize'] = 'modified'
    actions['Access Sys Sec'] = 'read'
    actions['Read Data'] = 'read'
    actions['Write Data'] = 'modified'
    actions['Append Data'] = 'modified'
    actions['Read EA'] = 'read'
    actions['Write EA'] = 'modified'
    actions['Execute/Traverse'] = 'read'
    actions['Read Attributes'] = 'read'
    actions['Write Attributes'] = 'acl_modified'
    actions['Query Key Value'] = 'read'
    actions['Set Key Value'] = 'modified'
    actions['Create Sub Key'] = 'created'
    actions['Enumerate Sub-Keys'] = 'read'
    actions['Notify About Changes to Keys'] = 'read'
    actions['Create Link'] = 'created'
    actions['Print'] = 'read'

    return actions


def _build_windows_event(alert, change):
    """"
    Helper function that builds the event dict on Windows hosts"
    """
    if alert['Hash'] == 'Item is a directory':
        object_type = 'directory'
    else:
        object_type = 'file'
    actions = _build_windows_actions()

    event = {'action': actions[change],
             'change_type': 'filesystem',
             'object_category': object_type,
             'object_path': alert['Object Name'],
             'file_name': os.path.basename(alert['Object Name']),
             'file_path': os.path.dirname(alert['Object Name'])}

    return event


def _build_linux_event(alert, change):
    """
    Helper function that builds the event dict on Linux hosts
    """
    if len(alert['change'].split('|')) == 2:
        object_type = 'directory'
    else:
        object_type = 'file'
    actions = _build_linux_actions()

    event = {'action': actions[change],
             'change_type': 'filesystem',
             'object_category': object_type,
             'object_path': alert['path'],
             'file_name': alert['name'],
             'file_path': alert['tag']}
    if 'contents' in alert:
        event['contents'] = alert['contents']

    if alert['stats']:  # Gather more data if the change wasn't a delete
        stats = alert['stats']
        event['object_id'] = stats['inode']
        event['file_acl'] = stats['mode']
        event['file_create_time'] = stats['ctime']
        event['file_modify_time'] = stats['mtime']
        event['file_size'] = stats['size'] / 1024.0  # Convert bytes to kilobytes
        event['user'] = stats['user']
        event['group'] = stats['group']
        if object_type == 'file':
            event['file_hash'] = alert['checksum']
            event['file_hash_type'] = alert['checksum_type']

    return event


def _build_alerts(data):
    """
    Helper function that extracts all the alerts from data and returns them as a list
    """
    alerts = []
    for item in data:
        events = item
        if not isinstance(events, list):
            events = [events]
        alerts.extend(events)

    return alerts
