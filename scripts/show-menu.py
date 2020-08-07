#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import glob
import json
import os
import sys

import common

from pick import pick


def write_config():
    with open(config_file, 'w') as f:
        config.write(f)
        f.flush()
        os.fsync(f.fileno())

def main_menu():
    title = f'Main - {__name__}'
    options = ['Images', 'Options', 'Shutdown']
    while True:
        option, _ = pick(options, title)
        if option == 'Images':
            images_menu()
        elif option == 'Options':
            options_menu()
        else:
            os.system('sudo shutdown -h now')

def images_menu():
    title = f'Images - {__name__}'
    options = [
            'List by image name',
            'List by board name',
            'List by model name',
        ]
    _, index = pick(options, title)
    if index == 0:
        image_folders = next(os.walk(f'{data_path}images'))[1]
        options = {}
        for image in image_folders:
            options[image] = image
    elif index in [1, 2]:
        data_files = glob.glob(f'{data_path}images/*/latest/data.json')
        if index == 1:
            field = 'boards'
        else:
            field = 'models'
        options = {}
        for data_file in data_files:
            with open(data_file, 'r') as f:
                data = json.load(f)
            image_name = data.get('image_name')
            for field_name in data.get(field):
                options[field_name] = image_name
    if config['default']['show_images'] == 'downloaded':
        dl_images = glob.glob(f'{data_path}images/*/*/*.bin')
        dl_images = [dl_image.split('/')[-3] for dl_image in dl_images]
        options = {key:val for key, val in options.items() if val in dl_images}
    title = 'Select an image'
    option, _ = pick(sorted(list(options.keys())), title)
    selected_image = options[option]
    options = next(os.walk(f'{data_path}images/{selected_image}'))[1]
    if config['default']['show_images'] == 'downloaded':
        dl_versions = glob.glob(f'{data_path}images/{selected_image}/*/*.bin')
        dl_versions = [dl_ver.split('/')[-2] for dl_ver in dl_versions]
        options = [option for option in options if option in dl_versions]
    options = sorted(options)
    selected_version, _ = pick(options, 'Select version')
    selected_dir = f'{data_path}images/{selected_image}/{selected_version}/'
    data_file = f'{selected_dir}data.json'
    with open(data_file, 'r') as f:
        data = json.load(f)
    while True:
      options = []
      image_file = f'{selected_dir}{data["file"]}'
      if os.path.isfile(image_file):
          options.append('Mount this image')
          options.append('Verify this image')
          options.append('Delete this image')
          options.append('Mount this image on boot')
      else:
          options.append('Download this image')
      option, _ = pick(options, f'{selected_image} - {selected_version}')
      if option == 'Mount this image':
        os.system('sudo rmmod g_mass_storage')
        if config['default']['mount_images'] == 'read-write':
          ro = 'n'
        else:
          ro = 'y'
        os.system(f'sudo modprobe g_mass_storage file="{image_file}" ro={ro}')
      elif option == 'Verify this image':
        md5_file = f'{image_file}.md5'
        cmd = f'bash -c "cd {selected_dir} && md5sum -c {md5_file}"'
        print(f'running {cmd}')
        return_code = os.system(cmd)
        if return_code == 0:
            print('File verification succeeded')
        else:
            print('File verification FAILED!')
        input('Press a key to continue')
      elif option == 'Delete this image':
        os.remove(image_file)
      elif option == 'Download this image':
        common.download_image_file(data, selected_dir) 

def options_menu():
    title = f'Options - {__name__}'
    while True:
      options = config_options + [{'name': 'Return to main menu'}]
      option, index = pick([option['name'] for option in options], title)
      if index == len(options) - 1:
          return
      set_option_menu(index)

def set_option_menu(option_index):
    print(option_index)
    option_target = config_options[option_index]['target']
    current_value = config['default'][option_target]
    current_value_index = config_options[option_index]['values'].index(current_value)
    title = config_options[option_index]['name']
    options = config_options[option_index]['values']
    selected_value, _ = pick(options, title)
    config['default'][option_target] = selected_value
    write_config()

__name__ = 'Universal Recovery Pi'
script_path, data_path = common.get_paths()
config_file = f'{data_path}config.ini'
config = configparser.ConfigParser()
config_options = [
        {
            'name': 'Mount images writable',
            'target': 'mount_images',
            'values': ['read-only', 'read-write'],
            'default_value': 'read-only'
        },
        {
            'name': 'Images to show',
            'target': 'show_images',
            'values': ['all', 'downloaded'],
            'default_value': 'all'
        }
    ]
config['default'] = {}
for config_option in config_options:
   config['default'][config_option['target']] = config_option.get('default_value', '')
config.read(config_file)
main_menu()
