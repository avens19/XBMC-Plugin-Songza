import json
import os
import sys
import time
import urllib
import urlparse
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs
import thread
from datetime import datetime
from resources.lib import requests
try:
    import StorageServer
except:
    from resources.lib import storageserverdummy as StorageServer

TEMP_CACHE = StorageServer.StorageServer('songza', 24)
CACHE_DIR = 'special://temp/songza/'
CACHED_JSON_FILE = CACHE_DIR + 'concierge.json'
CACHED_ICON_FILE = CACHE_DIR + '%s.jpg'
PLUGIN_URL = sys.argv[0] + '?'
HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
ADDONNAME = ADDON.getAddonInfo('name')
ICON = ADDON.getAddonInfo('icon')
FANART = ADDON.getAddonInfo('fanart')
USER = ADDON.getSetting('user')
PASSWORD = ADDON.getSetting('password')
THUMB_SIZE = ADDON.getSetting('thumb_size')
THUMB_AGE = ADDON.getSetting('thumb_age')
PRELOAD = ADDON.getSetting('preload')


def GetArguments():
    return urlparse.parse_qs((sys.argv[2])[1:])


def GetData(url, params=None):
    session = TEMP_CACHE.get('cookie')
    cookies = dict(sessionid=str(session))
    response = requests.get(url, params=params, cookies=cookies)
    cookies = requests.utils.dict_from_cookiejar(response.cookies)
    if 'sessionid' in cookies:
        TEMP_CACHE.set('cookie', cookies['sessionid'])
    if response.text == 'rate limit exceeded':
        warning = 'You can\'t skip songs that quickly.'
        display_time = 2000  # in milliseconds
        xbmc.executebuiltin('Notification(%s, %s, %d, %s)' % (ADDONNAME, warning, display_time, ICON))
        return None
    data = response.json()
    return data

def PostData(url,data=None):
    session = TEMP_CACHE.get('cookie')
    cookies = dict(sessionid=str(session))
    response = requests.post(url,data=data,cookies=cookies)
    cookies = requests.utils.dict_from_cookiejar(response.cookies)
    if 'sessionid' in cookies:
      TEMP_CACHE.set('cookie',cookies['sessionid'])
    return response.json()

def Login():
    USERID = TEMP_CACHE.get('userid')
    if USER != '' and PASSWORD != '' and USERID == '':
        xbmc.log('here')
        url = 'http://songza.com/api/1/login/pw'
        data = PostData(url,{'username':USER,'password':PASSWORD,'site':'songza'})
        TEMP_CACHE.set('userid',str(data['id']))
        xbmc.log(str(data['id']))

def StoreData(data):
    if not xbmcvfs.exists(CACHE_DIR):
        xbmcvfs.mkdir(CACHE_DIR)

    if xbmcvfs.exists(CACHED_JSON_FILE):
        xbmcvfs.delete(CACHED_JSON_FILE)

    dataFile = xbmcvfs.File(CACHED_JSON_FILE, 'w')
    dataFile.write(json.dumps(data))
    dataFile.close()


def GetStoredData():
    dataFile = xbmcvfs.File(CACHED_JSON_FILE)
    contents = dataFile.read()
    data = json.loads(contents[0:])
    dataFile.close()
    return data


def StoreIcon(icon_id):
    thumbnail_sizes = {
        '1': 50,
        '2': 100,
        '3': 200,
        '4': 500,
        '5': 1000
    }

    day_in_seconds = 24 * 60 * 60
    thumb_ages = {
        '1': day_in_seconds,
        '2': 2 * day_in_seconds,
        '3': 5 * day_in_seconds,
        '4': 15 * day_in_seconds,
        '5': 30 * day_in_seconds
    }

    if not xbmcvfs.exists(CACHE_DIR):
        xbmcvfs.mkdir(CACHE_DIR)

    filePath = CACHED_ICON_FILE % icon_id
    if xbmcvfs.exists(filePath):
        if THUMB_AGE == '0':
            return filePath

        info = os.stat(xbmc.translatePath(filePath))
        filetime = info.st_mtime
        now = time.time()
        diff = now - filetime
        limit = thumb_ages[THUMB_AGE] if THUMB_AGE else thumb_ages['5']

        if diff < limit:
            return filePath
        else:
            xbmcvfs.delete(filePath)

    size = thumbnail_sizes[THUMB_SIZE] if THUMB_SIZE else thumbnail_sizes['3']
    url = 'http://songza.com/api/1/station/%s/image?size=%s' % (icon_id, size)
    response = requests.get(url)
    if response.status_code == 200:
        dataFile = open(xbmc.translatePath(filePath), 'wb')
        for chunk in response.iter_content():
            dataFile.write(chunk)
        dataFile.close()
        response.close()

    return filePath


def AddMenuEntry(title, url=None, isFolder=True, description='', iconImage='DefaultMusicPlaylists.png', data=None):
    listItem = xbmcgui.ListItem(unicode(title), iconImage=iconImage)
    listItem.setInfo('music', {'title': title})
    listItem.setProperty('Album_Description', description)
    listItem.setProperty('fanart_image', FANART)
    listItem.setThumbnailImage(iconImage)
    USERID = TEMP_CACHE.get('userid')
    if not isFolder and USERID != '':
        listItem.addContextMenuItems([('Add to Songza list','XBMC.RunScript(special://home/addons/plugin.audio.songza/resources/lib/dialog.py,&user='+USERID+'&station=' + str(data)+')')])
    return xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=listItem, isFolder=isFolder)


def GenerateList(data, titleKey, queryParam, dataKey, descriptionKey=None, iconKey=None, isFolder=True, conditionalKey=None, conditionalValue=None, extraData=None):
    for item in data:
        title = item[titleKey]
        url = PLUGIN_URL + urllib.urlencode({queryParam: item[dataKey]})
        if extraData is not None:
            url = url + '&station='+extraData
        description = item[descriptionKey] if descriptionKey is not None else ''
        icon = 'DefaultMusicPlaylists.png'
        if iconKey is not None and THUMB_SIZE != '0':
            icon = CACHED_ICON_FILE % item[iconKey]
        if conditionalKey is None or conditionalValue is None or item[conditionalKey] == conditionalValue:
            AddMenuEntry(title, url, isFolder, description, icon, item[dataKey])

    xbmcplugin.endOfDirectory(HANDLE)


def ListModes():
    Login()
    USERID = TEMP_CACHE.get('userid')
    if USERID == '':
        MODES[:] = [mode for mode in MODES if not mode['user_required']]
    GenerateList(MODES, 'name', 'mode', 'id')


def ListScenarios():
    current_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
    period = ((datetime.now().hour / 4) - 1) % 6
    if period == 5:
        day = datetime.now().isoweekday() - 1  # If period is late night, then set day to yesterday
    else:
        day = datetime.now().isoweekday() % 7

    url = 'http://songza.com/api/1/situation/targeted?current_date=%s&' % current_date
    params = urllib.urlencode({
        'day': day,
        'period': period,
        'device': 'web',
        'site': 'songza',
        'optimizer': 'default',
        'max_situations': 5,
        'max_stations': 3
    })

    data = GetData(url, params)
    StoreData(data)
    GenerateList(data, 'title', 'scenario', 'title')


def ListSituations(scenario):
    data = GetStoredData()

    for scenarioData in data:
        if scenarioData['title'] == scenario:
            GenerateList(scenarioData['situations'], 'title', 'stations', 'station_ids')


def ListCharts():
    data = [{'name': 'Trending', 'id': 'trending'}, {'name': 'This Year', 'id': 'all-time'}]
    GenerateList(data, 'name', 'chart', 'id')


def ListChartStations(chart):
    url = 'http://songza.com/api/1/chart/name/songza/%s' % chart
    data = GetData(url)
    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')


def ListCategories():
    url = 'http://songza.com/api/1/tags'
    data = GetData(url)
    GenerateList(data, 'name', 'tag', 'id')


def ListSubcategories(tag):
    url = 'http://songza.com/api/1/gallery/tag/%s' % tag
    data = GetData(url)
    GenerateList(data, 'name', 'stations', 'station_ids')


def ListStations(stations):
    url = 'http://songza.com/api/1/station/multi?'

    params = ''
    keys = []
    for i in range(len(stations)):
        keys.append('id')
    ids = zip(keys, stations)
    params = urllib.urlencode(ids)

    data = GetData(url, params)

    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')
    thread.start_new_thread(GetAlbumCovers,(data,'id',))


def PlayStation(station):
    # Get and clear the music playlist
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()

    TEMP_CACHE.set('station', str(station))

    if(TEMP_CACHE.get('flag') == 't'):
        time.sleep(3)

    # Queue the next song
    track = QueueNextTrack(playlist, station)

    AddStationToRecent(station,track)

    TEMP_CACHE.set('flag', 'f')

    # Start playing the playlist
    player = xbmc.Player()
    player.play(playlist)


def SearchStations():
    keyboard = xbmc.Keyboard()
    keyboard.doModal()
    query = keyboard.getText()
    if (query == ''):
        return

    url = 'http://songza.com/api/1/search/station?query=%s' % query
    data = GetData(url)
    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')


def SearchArtists():
    keyboard = xbmc.Keyboard()
    keyboard.doModal()
    query = keyboard.getText()
    if (query == ''):
        return

    url = 'http://songza.com/api/1/search/artist?query=%s' % query
    data = GetData(url)
    GenerateList(data, 'name', 'artist', 'id')


def ListArtistsStations(artistid):
    url = 'http://songza.com/api/1/artist/%s/stations' % artistid
    data = GetData(url)
    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')


def ListRecent():
    USERID = TEMP_CACHE.get('userid')
    url = 'http://songza.com/api/1/user/%s/stations?limit=40&recent=1' % USERID
    data = GetData(url)
    GenerateList(data['recent']['stations'], 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')


def ListMyPlaylists():
    USERID = TEMP_CACHE.get('userid')
    url = 'http://songza.com/api/1/collection/user/%s' % USERID
    data = GetData(url)
    GenerateList(data, 'title', 'stations', 'station_ids')


def QueueNextTrack(playlist, station):
    next = GetData('http://songza.com/api/1/station/%s/next' % station)

    if next is None:
        return

    # Create ListItem from next song info
    listItem = xbmcgui.ListItem(unicode(next['song']['title']), unicode(next['song']['artist']['name']))
    listItem.setInfo('music', {'duration': next['song']['duration'], 'genre': next['song']['genre'], 'album': next['song']['album'], 'artist': next['song']['artist']['name'], 'title': next['song']['title']})
    listItem.setThumbnailImage(next['song']['cover_url'])

    # Need to add codec info for XBMC to pick the correct player
    listItem.addStreamInfo('audio', {'codec': 'mp3'})

    url = PLUGIN_URL + 'station=' + str(station) + '&play=' + urllib.quote(next['listen_url'])
    playlist.add(url, listItem)

    return next['song']['id']

def AddStationToRecent(station,track):
    USERID = TEMP_CACHE.get('userid')
    if USERID != '':
        url = str.format('http://songza.com/api/1/station/{0}/song/{1}/notify-play',station,track)
        PostData(url)


def PlayTrack(station, url):
    # Tell XBMC which URL to stream the song from
    listItem = xbmcgui.ListItem(path=url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listItem)

    if(TEMP_CACHE.get('flag') == 'f'):
        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        TEMP_CACHE.set('flag', 't')
        # Queue the next song from the station
        try:
            while playlist.getposition() > (len(playlist) - int(float(PRELOAD)) - 1) and TEMP_CACHE.get('station') == station:
                time.sleep(3)
                if(TEMP_CACHE.get('station') == station):
                    QueueNextTrack(playlist, station)
        finally:
            TEMP_CACHE.set('flag', 'f')

def GetAlbumCovers(data, iconKey):
    for item in data:
        StoreIcon(item[iconKey])
    return

MODES = [
    {'id': '1', 'name': 'Concierge', 'handler': ListScenarios, 'user_required': False},
    {'id': '2', 'name': 'Popular', 'handler': ListCharts, 'user_required': False},
    {'id': '3', 'name': 'Browse', 'handler': ListCategories, 'user_required': False},
    {'id': '4', 'name': 'Recent', 'handler': ListRecent, 'user_required': True},
    {'id': '5', 'name': 'My Playlists', 'handler': ListMyPlaylists, 'user_required': True},
    {'id': '6', 'name': 'Search Stations', 'handler': SearchStations, 'user_required': False},
    {'id': '7', 'name': 'Search Artists', 'handler': SearchArtists, 'user_required': False}
]

args = GetArguments()

if 'play' in args:
    PlayTrack(args['station'][0], args['play'][0])
elif 'station' in args:
    PlayStation(args['station'][0])
elif 'stations' in args:
    ListStations(json.loads(args['stations'][0]))
elif 'chart' in args:
    ListChartStations(args['chart'][0])
elif 'tag' in args:
    ListSubcategories(args['tag'][0])
elif 'scenario' in args:
    ListSituations(urllib.unquote(args['scenario'][0]))
elif 'artist' in args:
    ListArtistsStations(args['artist'][0])
elif 'mode' in args:
    (mode['handler']() for mode in MODES if mode['id'] == args['mode'][0]).next()
else:
    ListModes()
