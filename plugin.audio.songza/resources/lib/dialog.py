import json
import sys
import urllib
import urlparse
import xbmc
import os
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs
import time
from datetime import datetime
import requests
from requests import utils
from requests import cookies
try:
   import StorageServer
except:
   import storageserverdummy as StorageServer

TEMP_CACHE = StorageServer.StorageServer("songza", 24)

def GetArguments():
    return urlparse.parse_qs((sys.argv[1])[1:])

def GetData(url, params=None):
  session = TEMP_CACHE.get("cookie")
  cookies = dict(sessionid=str(session))
  r = requests.get(url, params=params,cookies=cookies)
  cookies = requests.utils.dict_from_cookiejar(r.cookies)
  if 'sessionid' in cookies:
      TEMP_CACHE.set("cookie",cookies['sessionid'])
  data = r.json()
  return data

def PostData(url,data=None):
  session = TEMP_CACHE.get("cookie")
  cookies = dict(sessionid=str(session))
  r = requests.post(url,data=data,cookies=cookies)
  cookies = requests.utils.dict_from_cookiejar(r.cookies)
  if 'sessionid' in cookies:
      TEMP_CACHE.set("cookie",cookies['sessionid'])
  xbmc.log(r.text)

args = GetArguments()
url = 'http://songza.com/api/1/collection/user/%s' % args['user'][0]
data = GetData(url)
titles = []
for i in range(len(data)):
  titles.append(data[i]['title'])
dialog = xbmcgui.Dialog()
ret = dialog.select('Choose a list', titles)
id = data[ret]['id']
url = "http://songza.com/api/1/collection/%s/add-station" % id
PostData(url,{"station":args['station'][0]})