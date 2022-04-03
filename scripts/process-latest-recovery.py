#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import errno
import json
import os
import re
import string
import sys

import common

FILENAME_SAFE_CHARS = string.ascii_letters + string.digits + '-_.() '

script_path, data_path = common.get_paths()

with open(f'{data_path}cros_versions.json') as f:
  cros_versions = json.load(f)
 
recovery_urls = [
                 'https://dl.google.com/dl/edgedl/chromeos/recovery/recovery.json',
                 'https://dl.google.com/dl/edgedl/chromeos/recovery/recovery2.json'.
                 'https://dl.google.com/dl/edgedl/chromeos/recovery/cloudready_recovery2.json',
                ]
seen_images = {}
p = r"_([^_]*)_recovery"
pdevice = r"^\^([a-zA-Z0-9]*)"
httpc = common.build_http()
for rec in recovery_urls:
    r = httpc.get(rec)
    images = r.json()
    i = 0
    for image in images:
        # file is uncompressed file, no .zip
        file = image.get('file')
        image_name = re.search(p, file)
        image_name = image_name.group(1)
        for suffix in ['-he',]:
            if image_name.endswith(suffix):
                image_name = image_name[:-len(suffix)]
        for prefix in ['x86-', 'veyron-', 'nyan-', 'daisy-', 'peach-', 'auron-']:
            if image_name.startswith(prefix):
                image_name = image_name[len(prefix):]
        board_name = re.search(pdevice, image.get('hwidmatch'))
        if board_name:
            board_name = board_name.group(1).lower()
        else:
            board_name = image_name
        if board_name == 'iec':
            board_name = 'mario'
        model = image.get('model', 'no model')
        manufacturer = image.get('manufacturer', 'no manufacturer')
        if manufacturer.lower() not in model.lower():
            model = f'{manufacturer} {model}'
        if image_name in seen_images:
            seen_images[image_name]['hwidmatches'].append(image.get('hwidmatch'))
            seen_images[image_name]['manufacturers'].append(manufacturer)
            seen_images[image_name]['models'].append(model)
            seen_images[image_name]['names'].append(image.get('name'))
            if board_name not in seen_images[image_name]['boards']:
                seen_images[image_name]['boards'].append(board_name)
                continue
            i += 1
        cros_version = int(image.get('version').split('.')[0])
        cr_version = int(cros_versions.get(str(cros_version), 0))
        image_data = {
          'image_name': image_name,
          'file': image.get('file'),
          'filesize': image.get('filesize'),
          'hwidmatches': [image.get('hwidmatch')],
          'manufacturers': [manufacturer],
          'md5': image.get('md5'),
          'models': [model],
          'names': [image.get('name')],
          'sha1': image.get('sha1'),
          'url': image.get('url'),
          'version': image.get('version'),
          'cros_version': int(cros_version),
          'boards': [board_name],
          'cr_version': int(cr_version),
          'zipfilesize': image.get('zipfilesize'),
          }
        seen_images[image_name] = image_data

for image, data in seen_images.items():
  ipath = f'{data_path}/images/{image}/'
  image_path = f'{ipath}{data.get("cr_version", 0)}'
  rel_image_path = f'../data/images/{image}/'
  cr_ver = data.get('cr_version', 0)
  rel_ver_path = f'{rel_image_path}{cr_ver}'
  os.makedirs(image_path, exist_ok=True)
  os.system(f'bash -c "cd {ipath} && ln -s -f {cr_ver} latest"')
  data_file = f'{image_path}/data.json'
  if not os.path.isfile(data_file):
    with open(data_file, 'w') as f:
      json.dump(data, f, indent=4, sort_keys=True)
