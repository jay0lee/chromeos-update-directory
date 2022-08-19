#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import glob
import json
import os
import random
import sys
from time import sleep, strftime

import common

from distutils.version import LooseVersion
import requests
import xmltodict


update_url = 'https://tools.google.com/service/update2'
global something_changed
something_changed = False

def getBoardUpdate(board_name, board_id, board_hwid, app_board, old_release='0.0.0.0', pinned_release='', channel='stable'):
    global something_changed
    if pinned_release:
        old_release = pinned_release
    # append .0.0 to old release if needed
    if len(old_release.split('.')) < 3:
        old_release = '%s.0.0' % old_release
    headers = {'Content-Type': 'application/xml'}
    latest_update_info = {}
    update_info = {}
    today = datetime.datetime.now()
    six_months_ago = (datetime.datetime.now() - datetime.timedelta(30*6))
    while True: # loop in case there are staggered updates
        request = f'''<?xml version="1.0" encoding="UTF-8"?>
  <request protocol="3.0" version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" installsource="ondemand" ismachine="1" testsource="prober">
  <app appid="{board_id}" version="{old_release}" board="{app_board}" track="{channel}-channel" hardware_class="{board_hwid}" delta_okay="false">
    <updatecheck targetversionprefix="{pinned_release}"></updatecheck>
  </app>
</request>'''
        retries = 3 
        for n in range(1, retries+1): # loop in case of network error
            try:
                response = requests.post(update_url, data=request, headers=headers)
            except Exception as e:
                continue
            xml_response_string = response.text
            json_response = dict(xmltodict.parse(xml_response_string))
            if (not 'response' in json_response) or ('@info' in json_response['response']['app']['updatecheck'] and json_response['response']['app']['updatecheck']['@info'] == 'rate limit'):
                wait_on_fail = min(2 ** n, 60) + float(random.randint(1, 1000)) / 1000
                sys.stdout.write(f'{n}...')
                sys.stdout.flush()
                sleep(wait_on_fail)
            else:
                break
            if n != retries+1:
                continue
        # See if we're just getting same data each time
        update_info['check_time'] = str(datetime.datetime.utcnow())
        update_info['request'] = request
        update_info['response'] = json.loads(json.dumps(xml_response_string))
        if update_info['response'] == latest_update_info.get('response'):
            break
        try:
            update_info['status'] = json_response['response']['app']['updatecheck']['@status']
        except KeyError:
          update_info['status'] = 'Unparsable response'
          return update_info
        if update_info['status'] != 'ok':
            break
        try:
            update_info['sample_hwid'] = board_hwid
            update_info['board_id'] = board_id
            update_info['app_board'] = app_board
            update_info['chromeos_version'] = json_response['response']['app']['updatecheck']['manifest']['actions']['action'][1]['@ChromeOSVersion']
            update_info['chrome_version'] = json_response['response']['app']['updatecheck']['manifest']['actions']['action'][1]['@ChromeVersion']
            update_info['size'] = int(json_response['response']['app']['updatecheck']['manifest']['packages']['package']['@size'])
            update_info['urls'] = []
            for codebase in json_response['response']['app']['updatecheck']['urls']['url']:
                update_info['urls'].append(codebase['@codebase'] + json_response['response']['app']['updatecheck']['manifest']['packages']['package']['@name'])
            update_info['sha256'] = json_response['response']['app']['updatecheck']['manifest']['packages']['package']['@hash_sha256']
            if channel == 'stable' and pinned_release == '':
                eol_date = json_response['response']['app']['updatecheck'].get('@_eol_date')
                if eol_date:
                    add_days = datetime.timedelta(days=int(eol_date))
                    epoch = datetime.datetime(1970,1,1)
                    eol_date = epoch + add_days
                    update_info['eol_date'] = str(eol_date)
                else:
                    # devices w/o eol_date in response are very_eol
                    eol_date = six_months_ago
                    print(f'  no eol data in {json_response["response"]["app"]["updatecheck"]}')
                update_info['eol'] = today >= eol_date
                update_info['very_eol'] = six_months_ago >= eol_date
        except (KeyError, IndexError) as e:
            pass
        latest_update_info = dict(update_info)
        old_release = update_info.get('chromeos_version')
        if not old_release:
            break
    # Ensure we are always setting eol and very_eol.
    # if we didn't get them, safe to assume device is
    # both
    if channel == 'stable' and pinned_release == '':
        for key in ['eol', 'very_eol']:
            if key not in latest_update_info:
                latest_update_info[key] = True
    return latest_update_info

def write_update_file(data_path, image, channel, update_data):
   global something_changed
   update_path = f'{data_path}/updates/{image}/{channel}'
   os.makedirs(update_path, exist_ok=True)
   update_file = f'{update_path}/data.json'
   write_update = False
   try:
      with open(update_file, 'r') as f:
         old_data = json.load(f)
         for item in ['chrome_version', 'chromeos_version', 'sha256']:
             if old_data.get(item) != update_data.get(item):
                 write_update = True
                 print(f'Writing update since {item} changed')
                 break
   except:
       print('writing update because exception occurred.')
       write_update = True
   if write_update:
       with open(update_file, 'w') as f:
           json.dump(update_data, f, indent=4, sort_keys=True)
       something_changed = True
   else:
       print('skipped writing update since no change')

def main():
    global something_changed
    script_path, data_path = common.get_paths()

    with open(f'{data_path}chrome_versions.json') as f:
        chrome_versions = json.load(f)

    pattern = f'{data_path}images/*/latest/data.json'
    data_files = glob.glob(pattern)
    data_files = [data_file for data_file in data_files]
    data_files.sort()
    newest_stable = 0
    i = 0
    count = len(data_files)
    images = {}
    eol_images = []
    very_eol_images = []
    for data_file in data_files:
            f = open(data_file, 'r')
            data = json.load(f)
            f.close()
            image = data['image_name']
            hwid = data['sample_hwid']
            board_id = data.get('chromeos_board_appid', data['chromeos_release_appid'])
            updates = {}
            updates['stable'] = getBoardUpdate(image,
                                    board_id,
                                    hwid,
                                    data['chromeos_release_board'])
            if updates['stable'].get('very_eol'):
                very_eol_images.append(image)
                print(f'skipping {image} which is well past EoL')
                continue
            else:
                print(f'{image} is eol {updates["stable"].get("eol_date")}')
            write_update_file(data_path, image, 'stable', updates['stable'])
            print(f'{image} stable {updates["stable"].get("chromeos_version")}')
            old_release = updates['stable'].get('chromeos_version', '0').split('.')[0]
            for channel in ['beta', 'dev', 'canary']:
                if channel == 'canary':
                    board_id = data.get('chromeos_canary_appid', '{01906EA2-3EB2-41F1-8F62-F0B7120EFD2E}')
                else:
                    board_id = data.get('chromeos_board_appid', data['chromeos_release_appid'])
                updates[channel] = getBoardUpdate(image,
                                                  board_id,
                                                  hwid,
                                                  data['chromeos_release_board'],
                                                  old_release=old_release,
                                                  channel=channel)
                write_update_file(data_path, image, channel, updates[channel])
                print(f'{image} {channel} {updates[channel].get("chromeos_version")}')
            stable_chrome_milestone = int(updates['stable'].get('chrome_version', '0').split('.')[0])
            if stable_chrome_milestone > newest_stable:
                newest_stable = stable_chrome_milestone
            images[image] = updates
    oldest_pin = newest_stable - 5
    for image in images:
        print(image)
        board_id = images[image]['stable']['board_id']
        hwid = images[image]['stable']['sample_hwid']
        app_board = images[image]['stable']['app_board']
        for chrome_milestone in range(oldest_pin, stable_chrome_milestone+1):
            chromeos_milestone = str(chrome_versions.get(str(chrome_milestone)))
            images[image][chrome_milestone] = getBoardUpdate(image,
                                                        board_id,
                                                        hwid,
                                                        app_board,
                                                        old_release='0.0.0.0',
                                                        channel='stable',
                                                        pinned_release=chromeos_milestone)
            write_update_file(data_path, image, chrome_milestone, images[image][chrome_milestone])

    #if something_changed:
    if True:
        # find most common versions
        versions = {}
        newest_versions = {}
        for image in images:
            for m in images[image]:
                chromeos_version = images[image][m].get('chromeos_version')
                if not chromeos_version:
                    continue
                versions[m] = versions.get(m, {})
                versions[m][chromeos_version] = versions[m].get(chromeos_version, 0) + 1
                current_newest = newest_versions.get(m)
                print(f'{image} {m} is {chromeos_version} greater than {current_newest} ?')
                if not current_newest or LooseVersion(chromeos_version) > LooseVersion(current_newest):
                    newest_versions[str(m)] = chromeos_version
        most_common_versions = {}
        for m in versions:
            for v in versions[m]:
                if m not in most_common_versions or versions[m].get(v, 0) > versions[m].get(most_common_versions[m], 0):
                    most_common_versions[str(m)] = v
        collected_versions = {'most_common': most_common_versions, 'newest': newest_versions}
        print(collected_versions)
        with open(f'{data_path}update_versions.json', 'w') as f:
            json.dump(collected_versions, f, indent=4, sort_keys=True)


if __name__ == '__main__':
  main()
