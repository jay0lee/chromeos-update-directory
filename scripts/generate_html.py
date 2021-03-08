#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import json
import os
import re

from distutils.version import LooseVersion

import common

script_path, data_path = common.get_paths()

with open(f'{data_path}/update_versions.json', 'r') as fd:
    cros_versions = json.load(fd)

most_common_versions = cros_versions.get('most_common', {})
newest_versions = cros_versions.get('newest', {})

html = '''<html>
  <head>
    <title>CrOS Updates Serving</title>
    <meta http-equiv="refresh" content="900">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="manifest" href="/manifest.json">
    <link rel="mask-icon" href="/safari-pinned-tab.svg" color="#5bbad5">
    <meta name="theme-color" content="#ffffff">
    <style>
      #header-fixed {
        position: fixed;
        top: 0px;
        display: none;
        background-color: white;
      }
    </style>
    <script type="text/javascript" src="//code.jquery.com/jquery-1.4.4.min.js"></script>
    <script>
      $(window).load(function() {
        var tableOffset = $("#cros-updates").offset().top;
        var $header = $("#cros-updates > thead").clone();
        $("#header-fixed").width($("#cros-updates").width());
        var $fixedHeader = $("#header-fixed").append($header);
        $("#cros-updates thead th").each(function(index) { $("#header-fixed thead th").eq(index).width($(this).width())});
        $(window).bind("scroll", function() {
          var offset = $(this).scrollTop();
          if (offset >= tableOffset && $fixedHeader.is(":hidden")) {
            $fixedHeader.show();
          } else if (offset < tableOffset) {
            $fixedHeader.hide();
          }
        });
      });


    </script>
  </head>
<body><font face="arial">

<table id="cros-updates" border="1">

<thead>
  <tr>
    <th>Codename</th>
'''

for version in most_common_versions:
    if version.isnumeric():
        version = f'Pinned {version}'
    html += f'<th>{version}</th>\n'
html += '''    <th>Recovery</th>
<th>Brand names</th>
  </tr>
</thead>
'''
pattern = f'{data_path}updates/*/'
boards = glob.glob(pattern)
boards = [board.split('/')[-2] for board in boards]
boards.sort()
for board in boards:
    html += f'<tr id="{board}"><td>{board}</td>'
    for common_version, version in most_common_versions.items():
        vdata_file = f'{data_path}updates/{board}/{common_version}/data.json'
        if not os.path.isfile(vdata_file):
            html += f'<td bgcolor="red">no update</td>'
        else:
            with open(vdata_file, 'r') as fd:
                vdata = json.load(fd)
            os_version = vdata.get('chromeos_version')
            if not os_version:
                html += f'<td bgcolor="red">unknown</td>'
            else:
                br_version = vdata.get('chrome_version', 'None')
                color = 'lightgreen'
                if LooseVersion(version) > LooseVersion(os_version):
                    color = 'orange'
                elif LooseVersion(version) < LooseVersion(os_version):
                    color = 'lightblue'
                html += f'<td bgcolor="{color}">{os_version}<br>{br_version}</td>'
    # this is where recovery/market name will go
    html += '<td></td><td></td></tr>\n'

html += '''</table>
<table id="header-fixed" border="1"></table>
<br>
Chart:
<table border="1">
<tr>
<td bgcolor="lightgreen"> most common version </td>
<td bgcolor="lightblue"> newer than most </td>
<td bgcolor="yellow"> minor version older </td>
<td bgcolor="orange"> major version older </td>
<td bgcolor="red"> no update </td>
</tr>
</table>
</font>
</body>
</html>
'''
with open(f'{data_path}../docs/index.html', 'w') as fd:
    fd.write(html)


