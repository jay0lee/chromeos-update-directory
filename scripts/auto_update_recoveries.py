#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import json
import os

import common


def download_image_file(data, path):
  rel_file = data.get('file')
  recovery_file = f'{path}/{rel_file}'
  return_data = {'full_file_path': recovery_file}
  recovery_file_md5 = f'{recovery_file}.md5'
  if os.path.isfile(recovery_file):
    return_data['needed_to_download'] = False
    return return_data
  else:
    url = data.get('url')
    url = f'http{url[5:]}' # http, not https for performance
    zip_md5 = data.get('md5')
    zip_md5_file = f'{recovery_file}.zip.md5'
    partial_file = f'{recovery_file}.part'
    partial_file_md5 = f'{partial_file}.md5'
    expected_size = int(data.get('filesize', 0))
    # Download, check compressed md5sum, unzip and create uncompressed md5sum all in one go
    # the main slowdown with each of these operations is reading/writing GBs worth of data
    # off the SD card so doing everything in parallel should save a lot of time.
    cmd = f'curl {url} | tee >(funzip | tee >(md5sum > {partial_file_md5}) > {partial_file}) | md5sum -c {zip_md5_file}'
    while True:
      with open(zip_md5_file, 'w') as f:
        f.write(f'{zip_md5} -')
      print(f'Downloading image {i}/{count}...')
      return_code = os.system(f'bash -c "{cmd}"')
      if return_code == 0 and os.path.getsize(partial_file) == expected_size:
        os.rename(partial_file, recovery_file)
        os.remove(zip_md5_file)
        with open(partial_file_md5, 'r') as f:
          uncompressed_md5 = f.readline().split(' ')[0]
        os.remove(partial_file_md5)
        with open(recovery_file_md5, 'w') as f:
          f.write(f'{uncompressed_md5} {rel_file}')
        break
      else:
        try:
          os.remove(partial_file)
        except FileNotFoundError:
          pass
        try:
          os.remove(zip_md5_file)
        except FileNotFoundError:
          pass
        print('FAILURE! Trying again...')
    return_data['needed_to_download'] = True
    return return_data

def main():
  script_path, data_path = common.get_paths()

  update_patterns_file = f'{data_path}auto_update_patterns.txt'

  partial_downloads = glob.glob(f'{data_path}/images/*/*/*.part')
  for partial_download in partial_downloads:
    print(f'removing partial download {partial_download}')
    try:
      os.remove(partial_download)
    except Exception as e:
      print('FAILURE: {e}')
      print('you may need to clean it up yourself')

  with open(update_patterns_file, 'r') as f:
    for _, pattern in enumerate(f):
      pattern = f'{data_path}{pattern}'.strip()
      data_files = list(set(glob.glob(pattern)))
      i = 0
      count = len(data_files)
      for data_file in data_files:
        i += 1
        print(f'Analyzing file {data_file}...')
        path = os.path.dirname(os.path.abspath(data_file))
        with open(data_file, 'r') as f:
          data = json.load(f)
          download_image_file(data, path)

if __name__ == 'main':
  main()
