#!/usr/bin/env python

import re
import math
import urllib # to download file
import os
import sys    # to determine platform 
import itertools

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
HEADER_DIR = 'header'
APNIC_URL = 'http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest'
NET_PATTERN = re.compile(
  r'^apnic\|CN\|ipv4\|([0-9.]+)\|(\d+)\|\d+\|a.*$', re.IGNORECASE)
PLATFORM_MAPPING = {
  'linux2': 'linux',
  'darwin': 'mac'
}
PLATFORM_META = {
  'linux': (
    'linux-ip-pre-up', 'route add -net %s/%d gw ${PREV_GW} metric 5\n',
    'linux-ip-down', 'route delete -net %s/%d gw ${PREV_GW} metric 5\n'
  ),
  'mac': (
    'mac-ip-up', 'route add %s/%d ${PREV_GW}\n',
    'mac-ip-down', 'route delete %s/%d ${PREV_GW}\n'
  )
}

def locate_apnic_path(filename = 'delegated-apnic-latest'):
  '''
  first, try find file in the current directory
  if not found, try find file in script directory
  if both not found, try download file to script directory
  '''
  if os.path.exists(filename): 
    return filename
  apnic_path = os.path.join(SCRIPT_DIR, filename)
  if not os.path.exists(apnic_path): 
    print 'Download apnic file from %s to %s' % (APNIC_URL, apnic_path)
    urllib.urlretrieve(APNIC_URL, apnic_path)
  return apnic_path

def parse_cn_net(apnic_path):
  '''
  parse china net(IP, routing prefix) from apnic file, 
  '''
  with open(apnic_path) as lines:
    for line in lines:
      m = NET_PATTERN.match(line)
      if not m: continue
      # (IP, routing prefix), e.g (1.2.3.4, 24) means 1.2.3.4/24
      yield (m.group(1), 32 - int(math.log(int(m.group(2)), 2)))

def load_excluding_net(filename = 'excluding_net'):
  '''
  load excluding net from file 'excluding_net'
  comment line starts with #
  empty line is available
  net format: IP or CIDR
  IP is treated as IP/32
  return format (IP, routing prefix)
  '''
  filepath = os.path.join(SCRIPT_DIR, filename)
  if os.path.exists(filepath):
    with open(filepath) as lines:
      for line in lines:
        if line.startswith('#'): continue # skip comment
        host_or_cidr = line.rstrip() # remove line break
        if not host_or_cidr: continue # skip empty line
        i = host_or_cidr.find('/')
        if i < 0: # host
          yield (host_or_cidr, 32)
        else:
          yield (host_or_cidr[:i], int(host_or_cidr[(i + 1):]))

class RouteScript:
  '''
  A helper class for generating route script
  '''
  def __init__(self, name, cmd_pattern):
    self.cmd_pattern = cmd_pattern
    self.script = open(name, 'w')
    header_path = os.path.join(SCRIPT_DIR, HEADER_DIR, name)
    if os.path.exists(header_path):
      with open(header_path) as f:
        self.script.write(f.read())

  def append(self, cidr):
    self.script.write(self.cmd_pattern % cidr)

  def close(self):
    self.script.close()

def generate(platform):
  '''
  generate route script
  '''
  config = PLATFORM_META[platform]
  up_script = RouteScript(config[0], config[1])
  down_script = RouteScript(config[2], config[3])
  for cidr in itertools.chain(
      load_excluding_net(), parse_cn_net(locate_apnic_path())):
    up_script.append(cidr)
    down_script.append(cidr)
  up_script.close()
  down_script.close()

def determine_platform():
  '''
  determine platform
  if argument present, return it
  or determine by sys.platform
  '''
  if len(sys.argv) > 1:
    return sys.argv[1]
  key = sys.platform
  return PLATFORM_MAPPING.get(key) or key

if __name__ == '__main__':
  platform = determine_platform()
  if platform in PLATFORM_META:
    generate(platform)
  else: 
    print >>sys.stderr, 'unsupported platform [%s], or you can specify one' % platform
