#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import json
import os
import pathlib
import re
import subprocess
import sys
from time import sleep

import rstr

import common 


analysis_version = 7

script_path, data_path = common.get_paths()
paycheck_path = '~/update_engine/scripts/paycheck.py'
mnt_path = f'{data_path}mnt/'
lsb_path = f'{mnt_path}etc/lsb-release'
modules_path = pathlib.Path(f'{mnt_path}lib/modules/')
crostini_path = f'{mnt_path}usr/bin/crostini_client'
parallels_path = f'{mnt_path}opt/google/dlc/pita/package/imageloader.json'

with open(f'{data_path}android_versions.json', 'r') as f:
  android_versions = json.load(f)

pattern = f'{data_path}updates/*/*/data.json'
data_files = glob.glob(pattern)
i = 0
count = len(data_files)
for data_file in data_files:
  i += 1
  subprocess.run(['sudo', 'losetup', '--detach-all'])
  path = os.path.dirname(os.path.abspath(data_file))
  with open(data_file, 'r') as f:
    data = json.load(f)
  if data.get('analysis_version', 0) >= analysis_version:
    print(f'Analysis for {data_file} is up to date')
    continue
  elif not data.get('urls'):
      print(f'no download URLs for {data_file}')
      continue
  else:
    data['analysis_version'] = analysis_version
  if '_delta_' in data['urls'][0]:
      print(f'  WARNING: cowardly refusing to analyze {data["urls"][0]} which appears to be a delta file. We should only be seeing non-delta images...')
      continue
  dl_results = common.download_update_file(data, path)
  delete_download = dl_results.get('needed_to_download', False)
  update_file_path = dl_results.get('full_file_path')
  partition_file = dl_results.get('partition_file')
  
  common.mount_image(partition_file, mnt_path, partition=0)

  # /etc/lsb-release contains interesting image details
  with open(lsb_path, 'r') as f:
    lsb_data = f.read().splitlines()
  for line in lsb_data:
    key, value = line.split('=')
    data[key.lower()] = value

  # /lib/modules/ subdirectories are the kernel version(s) of image
  data['linux_kernel_versions'] = [f.name for f in modules_path.iterdir() if f.is_dir()]

  # if chromeos_arc_android_sdk_version is set in /etc/lsb-release, Android apps are supported
  data['android_app_support'] = bool(data.get('chromeos_arc_android_sdk_version'))
  if data['android_app_support']:
    data['android_version'] = android_versions.get(data['chromeos_arc_android_sdk_version'], 'Unknown')

  # if /usr/sbin/crostini-client exists, Linux VMs are supported
  data['crostini_support'] = os.path.isfile(crostini_path)
  
  # if /opt/google/dlc/pita/package/imageloader.json exists, Parallels is supported in certain configs
  data['parallels_support'] = os.path.isfile(parallels_path)

  with open(data_file, 'w') as f:
    json.dump(data, f, indent=4, sort_keys=True)

  common.unmount_image(mnt_path)

  if delete_download:
    sleep(1)
    delete_pattern = f'{update_file_path}*'
    data_files = glob.glob(delete_pattern)
    i = 0
    count = len(data_files)
    for data_file in data_files:
        os.remove(data_file)
  
