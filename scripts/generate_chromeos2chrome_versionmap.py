#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re

import common

cros_tags_url = 'https://chromium.googlesource.com/chromiumos/manifest/+refs?format=TEXT'
httpc = common.build_http()
r = httpc.get(cros_tags_url)

branches = r.text
p = re.compile(r"^.*release-R([0-9]*)-([0-9]*).*$", re.MULTILINE)
m = p.findall(branches)
chrome_versions = {}
cros_versions = {}
for match in m:
  chrome_version = int(match[0])
  cros_version = int(match[1])
  chrome_versions[chrome_version] = cros_version
  cros_versions[cros_version] = chrome_version

script_path, data_path = common.get_paths()

cversions_json = f'{data_path}chrome_versions.json'
crosversions_json = f'{data_path}cros_versions.json'

print(f'Writing chrome>chromeos versin map to {cversions_json}')
with open(cversions_json, 'w') as cversions_file:
  json.dump(chrome_versions, cversions_file, indent=4, sort_keys=True)

print(f'Writing chromeos>chrome version map to {crosversions_json}')
with open(crosversions_json, 'w') as crosv_file:
  json.dump(cros_versions, crosv_file, indent=4, sort_keys=True)
