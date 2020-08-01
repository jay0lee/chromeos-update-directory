#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import errno
import json
import os
import re
import string
import sys

from lxml import html as lhtml
from lxml import etree

import common

FILENAME_SAFE_CHARS = string.ascii_letters + string.digits + '-_.() '

script_path, data_path = common.get_paths()

with open(f'{data_path}cros_versions.json') as f:
  cros_versions = json.load(f)
with open(f'{data_path}chrome_versions.json') as f:
  cr_versions = json.load(f)

recovery_url = 'https://dl.google.com/dl/edgedl/chromeos/recovery/recovery.json'
httpc = common.build_http()
r = httpc.get(recovery_url)
images = r.json()
seen_images = {} 
i = 0

cros_updates_url = 'https://cros-updates-serving.appspot.com/'
r = httpc.get(cros_updates_url)
cu_html = r.content
cu_data = lhtml.fromstring(cu_html)
table = cu_data.get_element_by_id('cros-updates')
old_recs = {}
for row in iter(table):
  if len(row) < 2:
    continue
  image_name = row[0][0].text
  old_recs[image_name] = {} 
  recoveries = row[-2]
  for link in recoveries.getchildren():
    cr_ver = link.text
    for l in link.iterlinks():
      url = l[2]
    old_recs[image_name][cr_ver] = url

p = r"_([^_]*)_recovery"
pdevice = r"^\^([a-zA-Z0-9]*)"
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
    'hwidmatches': [image.get('hwidmatch')],
    'manufacturers': [manufacturer],
    'models': [model],
    'names': [image.get('name')],
    'boards': [board_name],
  }
  
  seen_images[image_name] = image_data

for image, data in seen_images.items():
  ipath = f'{data_path}/images/{image}/'
  if image not in old_recs:
    print(f'no recoveries for {image}')
    continue
  else:
    print(f'processing {image} versions {",".join(old_recs[image])}')
  for old_rec_ver, url in old_recs[image].items():
    if old_rec_ver in [83, '83']:
      continue
    image_path = f'{ipath}{old_rec_ver}'
    rel_image_path = f'../data/images/{image}/'
    rel_ver_path = f'{rel_image_path}{old_rec_ver}'
    os.makedirs(image_path, exist_ok=True)
    data['file'] = url.split('/')[-1][:-4]
    data['url'] = url
    data['version'] = cr_versions[old_rec_ver]
    data['cros_version'] = cr_versions[old_rec_ver]
    data['cr_version'] = int(old_rec_ver)
    data_file = f'{image_path}/data.json'
    print(data_file)
    with open(data_file, 'w') as f:
      json.dump(data, f, indent=4, sort_keys=True)
