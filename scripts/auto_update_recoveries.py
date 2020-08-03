#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import json
import os

import common

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
          common.download_image_file(data, path)

if __name__ == 'main':
  main()
