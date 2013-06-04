import json
import sys
import urllib
import urlparse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
from datetime import datetime
from resources.lib import requests

CACHED_JSON_FILE = 'songza.json'
PLUGIN_URL = sys.argv[0] + '?'
HANDLE = int(sys.argv[1])
MODES = {
    'Concierge': 1,
    'Popular': 2,
    'Browse': 3
}


def GetArguments():
    return urlparse.parse_qs((sys.argv[2])[1:])


def GetData(url, params=None):
    data = requests.get(url, params=params).json()
    return data


def StoreData(data):
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


def AddMenuEntry(title, url=None, isFolder=True, iconImage='DefaultMusicPlaylists.png'):
    listItem = xbmcgui.ListItem(unicode(title), iconImage=iconImage)
    listItem.setInfo('music', {'title': title})
    listItem.setThumbnailImage(iconImage)
    if url is None:
        url = PLUGIN_URL + 'mode=%s' % MODES[title]
    return xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=listItem, isFolder=isFolder)


def RootMenu():
    for key, val in MODES.items():
        AddMenuEntry(key)
    xbmcplugin.endOfDirectory(HANDLE)


def GenerateList(data, titleKey, queryParam, dataKey, iconKey=None, isFolder=True, conditionalKey=None, conditionalValue=None):
    for item in data:
        title = item[titleKey]
        url = PLUGIN_URL + urllib.urlencode({queryParam: item[dataKey]})
        if conditionalKey is None or conditionalValue is None or item[conditionalKey] == conditionalValue:
            if iconKey is None:
                AddMenuEntry(title, url, isFolder)
            else:
                AddMenuEntry(title, url, isFolder, item[iconKey])

    xbmcplugin.endOfDirectory(HANDLE)


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
    GenerateList(data, 'name', 'station', 'id', 'cover_url', False, 'status', 'NORMAL')


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

    GenerateList(data, 'name', 'station', 'id', 'cover_url', False, 'status', 'NORMAL')


def PlayStation(station):
    # Get and clear the music playlist
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()

    # Queue two songs so that there is no delay for next song info when skipping
    QueueNextTrack(playlist, station)
    QueueNextTrack(playlist, station)

    # Start playing the playlist
    player = xbmc.Player()
    player.play(playlist)


def QueueNextTrack(playlist, station):
    next = GetData('http://songza.com/api/1/station/%s/next' % station)

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
    if playlist.getposition() > (len(playlist) - 3):
        QueueNextTrack(playlist, station)


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
elif 'mode' in args:
    if int(args['mode'][0]) == 1:  # Concierge
        ListScenarios()
    elif int(args['mode'][0]) == 2:  # Popular
        ListCharts()
    elif int(args['mode'][0]) == 3:  # Browse
        ListCategories()
else:
    RootMenu()
