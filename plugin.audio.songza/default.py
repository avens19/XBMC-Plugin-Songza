import json
import sys
import urllib
import urlparse
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs
import time
from datetime import datetime
from resources.lib import requests
from resources.lib.requests import utils
from resources.lib.requests import cookies

CACHE_DIR = 'special://temp/songza/'
CACHED_JSON_FILE = CACHE_DIR + 'concierge.json'
CACHED_COOKIES_FILE = CACHE_DIR + 'cookies'
CACHED_ICON_FILE = CACHE_DIR + '%s.jpg'
PLUGIN_URL = sys.argv[0] + '?'
HANDLE = int(sys.argv[1])
ADDON       = xbmcaddon.Addon()
ADDONNAME   = ADDON.getAddonInfo('name')
ICON        = ADDON.getAddonInfo('icon')
USERID = ADDON.getSetting('userid')
THUMB = ADDON.getSetting('thumb')

def GetArguments():
    return urlparse.parse_qs((sys.argv[2])[1:])


def GetData(url, params=None):
    session = LoadSession()
    cookies = dict(sessionid=str(session))
    r = requests.get(url, params=params, cookies=cookies)
    cookies = requests.utils.dict_from_cookiejar(r.cookies)
    if 'sessionid' in cookies:
        StoreSession(cookies['sessionid'])
    if r.text == 'rate limit exceeded':
        line1 = "You can't skip songs that quickly"
        time = 2000  #in miliseconds
        xbmc.executebuiltin('Notification(%s, %s, %d, %s)'%(ADDONNAME,line1, time, ICON))
        return None
    data = r.json()
    return data


def StoreSession(session):
    if not xbmcvfs.exists(CACHE_DIR):
        xbmcvfs.mkdir(CACHE_DIR)

    if xbmcvfs.exists(CACHED_COOKIES_FILE):
        xbmcvfs.delete(CACHED_COOKIES_FILE)
        
    dataFile = xbmcvfs.File(CACHED_COOKIES_FILE, 'w')
    dataFile.write(session)
    dataFile.close()

def LoadSession():
    if not xbmcvfs.exists(CACHED_COOKIES_FILE):
        return None

    dataFile = xbmcvfs.File(CACHED_COOKIES_FILE)
    session = dataFile.read()
    dataFile.close()
    return session

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


def StoreIcon(id):
    if THUMB == "0":
        return None
    elif THUMB == "1":     #50 px
        size = 50
    elif THUMB == "2":     #100 px
        size = 100
    elif THUMB == "3":     #200 px
        size = 200
    elif THUMB == "4":     #500 px
        size = 500
    elif THUMB == "5":     #1000 px
        size = 1000
    else:
        size = 200

    if not xbmcvfs.exists(CACHE_DIR):
        xbmcvfs.mkdir(CACHE_DIR)

    filePath = CACHED_ICON_FILE % id
    if xbmcvfs.exists(filePath):
        #TODO: Delete and refresh if X age - xbmcvfs.delete(filePath)
        return filePath

    url = 'http://songza.com/api/1/station/{0}/image?size={1}'.format(id,size)
    response = requests.get(url)
    if response.status_code == 200:

        dataFile = open(xbmc.translatePath(filePath), 'wb')
        for chunk in response.iter_content():
            dataFile.write(chunk)
        dataFile.close()
        response.close()

    return filePath


def AddMenuEntry(title, url=None, isFolder=True, description='', iconImage='DefaultMusicPlaylists.png'):
    listItem = xbmcgui.ListItem(unicode(title), iconImage=iconImage)
    listItem.setInfo('music', {'title': title})
    listItem.setProperty('Album_Description', description)
    listItem.setThumbnailImage(iconImage)
    return xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=listItem, isFolder=isFolder)


def GenerateList(data, titleKey, queryParam, dataKey, descriptionKey=None, iconKey=None, isFolder=True, conditionalKey=None, conditionalValue=None):
    for item in data:
        title = item[titleKey]
        url = PLUGIN_URL + urllib.urlencode({queryParam: item[dataKey]})
        description = item[descriptionKey] if descriptionKey is not None else ''
        icon = 'DefaultMusicPlaylists.png'
        if iconKey is not None and THUMB != "0":
            icon = StoreIcon(item[iconKey])
        if conditionalKey is None or conditionalValue is None or item[conditionalKey] == conditionalValue:
            AddMenuEntry(title, url, isFolder, description, icon)

    xbmcplugin.endOfDirectory(HANDLE)


def ListModes():
    if(USERID == ""):
        data = [{'name': 'Concierge', 'id': 1}, {'name': 'Popular', 'id': 2}, {'name': 'Browse', 'id': 3}, {'name': 'Search Playlists', 'id': 4}, {'name': 'Search Artists', 'id': 5}]
    else:
        data = [{'name': 'Concierge', 'id': 1}, {'name': 'Popular', 'id': 2}, {'name': 'Browse', 'id': 3}, {'name': 'Recent', 'id': 4}, {'name': 'My Playlists', 'id': 5}, {'name': 'Search Playlists', 'id': 6}, {'name': 'Search Artists', 'id': 7}]

    GenerateList(data, 'name', 'mode', 'id')


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

    if xbmcvfs.exists(CACHED_COOKIES_FILE):
        xbmcvfs.delete(CACHED_COOKIES_FILE)

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


def PlayStation(station):
    # Get and clear the music playlist
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()

    # Queue the next song
    QueueNextTrack(playlist, station)

    # Start playing the playlist
    player = xbmc.Player()
    player.play(playlist)



def QueueNextTrack(playlist, station):
    next = GetData('http://songza.com/api/1/station/%s/next' % station)

    if next is None:
        return

    xbmc.log('Song queued: ' + next['song']['title'])

    # Create ListItem from next song info
    listItem = xbmcgui.ListItem(unicode(next['song']['title']), unicode(next['song']['artist']['name']))
    listItem.setInfo('music', {'duration': next['song']['duration'], 'genre': next['song']['genre'], 'album': next['song']['album'], 'artist': next['song']['artist']['name'], 'title': next['song']['title']})
    listItem.setThumbnailImage(next['song']['cover_url'])

    # Need to add codec info for XBMC to pick the correct player
    listItem.addStreamInfo('audio', {'codec': 'mp3'})

    url = PLUGIN_URL + 'station=' + str(station) + '&play=' + urllib.quote(next['listen_url'])
    playlist.add(url, listItem)


def PlayTrack(station, url):
    # Tell XBMC which URL to stream the song from
    listItem = xbmcgui.ListItem(path=url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listItem)

    # Queue the next song from the station
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    while playlist.getposition() > (len(playlist) - 3):
        time.sleep(3)
        QueueNextTrack(playlist, station)

def SearchPlaylists():
    keyboard = xbmc.Keyboard()
    keyboard.doModal()
    query = keyboard.getText()
    if (query == ""):
        return

    url = 'http://songza.com/api/1/search/station?query=%s' % query
    data = GetData(url)
    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')

def SearchArtists():
    keyboard = xbmc.Keyboard()
    keyboard.doModal()
    query = keyboard.getText()
    if (query == ""):
        return

    url = 'http://songza.com/api/1/search/artist?query=%s' % query
    data = GetData(url)
    GenerateList(data, 'name', 'artist', 'id')

def ListArtistsStations(artistid):
    url = 'http://songza.com/api/1/artist/%s/stations' % artistid
    data = GetData(url)
    GenerateList(data, 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')

def ListRecent():
    url = 'http://songza.com/api/1/user/%s/stations?limit=40&recent=1' % USERID
    data = GetData(url)
    GenerateList(data['recent']['stations'], 'name', 'station', 'id', 'description', 'id', False, 'status', 'NORMAL')

def ListMyPlaylists():
    url = 'http://songza.com/api/1/collection/user/%s' % USERID
    data = GetData(url)
    GenerateList(data, 'title', 'stations', 'station_ids')


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
    if int(args['mode'][0]) == 1:  # Concierge
        ListScenarios()
    elif int(args['mode'][0]) == 2:  # Popular
        ListCharts()
    elif int(args['mode'][0]) == 3:  # Browse
        ListCategories()
    elif int(args['mode'][0]) == 4:  # Recent
        ListRecent()
    elif int(args['mode'][0]) == 5:  # My Playlists
        ListMyPlaylists()
    elif int(args['mode'][0]) == 6:  # Search Playlists
        SearchPlaylists()
    elif int(args['mode'][0]) == 7:  # Search Artists
        SearchArtists()
else:
    ListModes()
