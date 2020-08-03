import __main__
import datetime
import os
import re
import subprocess
import sys

import xmltodict
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def build_http():
  retry_strategy = Retry(
      total=10,
      status_forcelist=[429, 500, 502, 503, 504],
      method_whitelist=["HEAD", "GET", "OPTIONS"]
  )
  adapter = HTTPAdapter(max_retries=retry_strategy)
  httpc = requests.Session()
  httpc.mount("https://", adapter)
  httpc.mount("http://", adapter)
  return httpc

def check_updates(appid, version, board, track, hardware_class, targetversionprefix='', installsource='ondemand'):
  xml_map = {
    'status': ['response', 'app', 'updatecheck', '@status'],
    'eol_date': ['response', 'app', 'updatecheck', '@_eol_date'],
    'chrome_version': ['response', 'app', 'updatecheck', 'manifest', 'actions', 'action', 1, '@ChromeVersion'],
    'chromeos_version': ['response', 'app', 'updatecheck', 'manifest', 'actions', 'action', 1, '@ChromeOSVersion'],
    }
  url = 'https://tools.google.com/service/update2'
  post_data = f'''<?xml version="1.0" encoding="UTF-8"?>
  <request protocol="3.0" version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" installsource="{installsource}" ismachine="1" testsource="prober">
  <app appid="{appid}" version="{version}" board="{board}" track="{track}" hardware_class="{hardware_class}" delta_okay="false">
    <updatecheck targetversionprefix="{targetversionprefix}"></updatecheck>
  </app>
</request>'''
  httpc = build_http()
  r = httpc.post(url, data=post_data)
  data = dict(xmltodict.parse(r.content))
  return_data = {}
  for item in xml_map:
    value = data
    for location in xml_map[item]:
      if type(location) is int or location in value:
        value = value[location]
      else:
        value = None
        break
    return_data[item] = value
  if return_data.get('eol_date'):
    add_days = datetime.timedelta(days=int(return_data['eol_date']))
    epoch = datetime.datetime(1970,1,1)
    return_data['eol_date'] = (epoch + add_days)
  return return_data

def download_image_file(data, path, verify=True, backfill_verify=False):
  rel_file = data.get('file')
  recovery_file = f'{path}/{rel_file}'
  return_data = {'full_file_path': recovery_file}
  if os.path.isfile(recovery_file):
    return_data['needed_to_download'] = False
    return return_data
  else:
    url = data.get('url')
    url = f'http{url[5:]}' # http, not https for performance
    zip_md5 = data.get('md5')
    recovery_file_md5 = f'{recovery_file}.md5'
    recovery_file_sha1 = f'{recovery_file}.sha1'
    recovery_file_zip = f'{recovery_file}.zip'
    zip_md5_file = f'{recovery_file}.zip.md5'
    zip_sha1_file = f'{recovery_file}.zip.sha1'
    partial_file = f'{recovery_file}.part'
    partial_file_md5 = f'{partial_file}.md5'
    partial_file_sha1 = f'{partial_file}.sha1'
    temp_files = [recovery_file_zip, zip_md5_file, zip_sha1_file, partial_file_md5, partial_file_sha1, partial_file]
    perm_files = [recovery_file_md5, recovery_file_sha1, partial_file, recovery_file]
    expected_size = int(data.get('filesize', 0))
    # Download, check compressed md5sum, unzip and create uncompressed md5sum all in one go
    # the main slowdown with each of these operations is reading/writing GBs worth of data
    # off the SD card so doing everything in parallel should save a lot of time.
    if verify:
      cmd = f'curl -s {url} | tee >(funzip | tee >(md5sum > {partial_file_md5}) > {partial_file}) | md5sum --quiet -c {zip_md5_file}'
      with open(zip_md5_file, 'w') as f:
        print(f'writing {zip_md5_file}...')
        f.write(f'{zip_md5} -')
    elif backfill_verify:
      # get size of file from web server
      expected_size = int(requests.get(url, stream=True).headers['Content-length'])
      cmd = f'curl -s {url} | tee >(md5sum > {zip_md5_file}) >(sha1sum > {zip_sha1_file}) {recovery_file_zip} | funzip | tee >(md5sum > {partial_file_md5}) >(sha1sum > {partial_file_sha1}) > {partial_file}'
    else:
      # just write it. Failures possible
      cmd = f'curl -s {url} | funzip > {partial_file}'
    while True:
      print(f'Downloading image {rel_file}...\n\n')
      return_code = os.system(f'bash -c "{cmd}"')
      if backfill_verify:
        downloaded_size = os.path.getsize(recovery_file_zip)
        print(f'downloaded_size: {downloaded_size}  expected_size: {expected_size}')
      else:
        downloaded_size = expected_size
      if return_code == 0 and ((not verify and not backfill_verify) or downloaded_size == expected_size):
        os.rename(partial_file, recovery_file)
        if backfill_verify:
          with open(zip_md5_file, 'r') as f:
            zip_md5 = f.read().strip().split(' ')[0]
          data['md5'] = zip_md5
          with open(zip_sha1_file, 'r') as f:
            zip_sha1 = f.read().strip().split(' ')[0]
          data['sha1'] = zip_sha1
        with open(partial_file_md5, 'r') as f:
          uncompressed_md5 = f.readline().split(' ')[0]
        with open(recovery_file_md5, 'w') as f:
          f.write(f'{uncompressed_md5} {rel_file}')
        for f in temp_files:
          try:
            os.remove(f)
          except FileNotFoundError:
            pass
        break
      else:
        for f in temp_files + perm_files:
          try:
            os.remove(f)
          except FileNotFoundError:
            pass
        print('FAILURE! Trying again...')
    return_data['needed_to_download'] = True
    return_data['data'] = data
    return return_data

def get_paths():
  main_file = __main__.__file__
  script_path = os.path.dirname(os.path.realpath(main_file))
  data_path = f'{script_path[:-7]}data/'
  return (script_path, data_path)

def mount_image(image_file, mnt_path, partition=3):
  # first drop any other mount that might be in place
  unmount_image(mnt_path)

  # confirm our mnt_path is not mounted
  return_code = os.system(f'mount | grep {mnt_path}')
  if return_code == 0:
    print(f'ERROR: tried to unmount {mnt_path} but it is still mounted')
    sys.exit(3)

  # confirm no loop devices currently exist
  #lodevices = str(subprocess.run(['sudo', 'losetup', '--all'], stdout=subprocess.PIPE).stdout)
  #if len(lodevices) > 3:
  #  print(f'ERROR: some loopback devices still exist and couldn\'t be removed:')
  #  print(lodevices)
  #  sys.exit(4)

  # Use fdisk to find start and end of the partition
  fdisk_cmd = ['bash', '-c', f'/sbin/fdisk -l {image_file} 2> /dev/null']
  fdisk_out = str(subprocess.run(fdisk_cmd, stdout=subprocess.PIPE).stdout)
  rx = f'{image_file}{partition}\s+([0-9]*)\s+([0-9]*)'
  mg = re.search(rx, fdisk_out)
  if not mg:
    print(f'ERROR: failed to find partition {partition} of {image_file} (does file exist?)')
    sys.exit(5)
  part_start = str(int(mg.group(1)) * 512)
  part_end = str(int(mg.group(2)) * 512)

  # setup loopback device /dev/loop0 and mount
  losetup_cmd = ['sudo', 'losetup', '--show', '--find', '--offset', part_start, '--sizelimit', part_end, image_file]
  loop_device = subprocess.run(losetup_cmd, stdout=subprocess.PIPE).stdout.strip()
  mount_cmd = ['sudo', 'mount', '-o', 'ro', loop_device, mnt_path]
  subprocess.run(mount_cmd)

def unmount_image(mnt_path, silent=True):
  umount_cmd = ['sudo', 'bash', '-c', f'umount {mnt_path}']
  if silent:
    umount_cmd[3] += ' 2> /dev/null'
  subprocess.run(umount_cmd)
  subprocess.run(['sudo', 'losetup', '--detach-all'])
