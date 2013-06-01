import json
import sys
import urllib
import urlparse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
from BeautifulSoup import BeautifulSoup
from datetime import datetime
from resources.lib import requests

CACHED_JSON_FILE = 'songza.json'
PLUGIN_URL = sys.argv[0] + '?'
HANDLE = int(sys.argv[1])
MODES = {
    'Music Concierge': 1,
    #TODO 'Popular': 2,
    'Browse': 3
}


def GetArguments():
    return urlparse.parse_qs((sys.argv[2])[1:])


def GetStoredData():
    dataFile = xbmcvfs.File(CACHED_JSON_FILE)
    contents = dataFile.read()
    data = json.loads(contents[0:])
    dataFile.close()
    return data


def AddMenuEntry(title, url=None, isFolder=True, iconImage='DefaultMusicPlaylists.png'):
    listItem = xbmcgui.ListItem(unicode(title), iconImage=iconImage)
    listItem.setInfo('music', {'title': title})
    if url is None:
        url = PLUGIN_URL + 'mode=%s' % MODES[title]
    return xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=listItem, isFolder=isFolder)


def RootMenu():
    for key, val in MODES.items():
        AddMenuEntry(key)
    xbmcplugin.endOfDirectory(HANDLE)


def ListScenarios():
    current_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
    url = 'http://songza.com/api/1/situation/targeted?current_date=%s&' % current_date
    params = urllib.urlencode({
        'day': 1,
        'period': 1,
        'device': 'web',
        'site': 'songza',
        'optimizer': 'default',
        'max_situations': 5,
        'max_stations': 3
    })
    data = GetData(url, params)

    if xbmcvfs.exists(CACHED_JSON_FILE):
        xbmcvfs.delete(CACHED_JSON_FILE)

    dataFile = xbmcvfs.File(CACHED_JSON_FILE, 'w')
    dataFile.write(json.dumps(data))
    dataFile.close()

    for scenario in data:
        title = scenario['title']
        url = PLUGIN_URL + urllib.urlencode({'scenario': title})
        AddMenuEntry(title, url, iconImage=scenario['icon'])
    xbmcplugin.endOfDirectory(HANDLE)


def ListSituations(scenario):
    data = GetStoredData()

    for scenarioData in data:
        if scenarioData['title'] == scenario:
            for situation in scenarioData['situations']:
                title = situation['title']
                url = PLUGIN_URL + urllib.urlencode({'scenario': scenario, 'situation': situation['id']})
                AddMenuEntry(title, url, iconImage=scenarioData['icon'])

    xbmcplugin.endOfDirectory(HANDLE)


def ListBrowseCategories():
    url = 'http://songza.com/discover/'
    soup = BeautifulSoup(GetHtml(url), convertEntities=BeautifulSoup.HTML_ENTITIES)
    parent = soup.findAll('ul', {'class': 'nav nav-tabs'})
    for link in parent[0].findAll('a'):
        title = link.string
        url = PLUGIN_URL + urllib.urlencode({'categoryUrl': 'http://songza.com' + link['href']})
        AddMenuEntry(title, url)
    xbmcplugin.endOfDirectory(HANDLE)


def ListBrowseSubcategories(categoryUrl):
    soup = BeautifulSoup(GetHtml(categoryUrl), convertEntities=BeautifulSoup.HTML_ENTITIES)
    parent = soup.findAll('div', {'class': 'szi-gallery-list'})
    for link in parent[0].findAll('a'):
        title = link.string
        url = PLUGIN_URL + urllib.urlencode({'subcategoryUrl': 'http://songza.com' + link['href']})
        AddMenuEntry(title, url)
    xbmcplugin.endOfDirectory(HANDLE)


def ListBrowseStations(subcategoryUrl):
    soup = BeautifulSoup(GetHtml(subcategoryUrl), convertEntities=BeautifulSoup.HTML_ENTITIES)
    parent = soup.findAll('div', {'class': 'szi-station-list'})
    for link in parent[0].findAll('a', {'itemprop': 'url'}):
        AddStation(link.string, link['data-sz-station-id'], 'http://songza.com/api/1/station/%s/image' % link['data-sz-station-id'])
    xbmcplugin.endOfDirectory(HANDLE)


def ListConciergeStations(scenario, situation):
    data = GetStoredData()
    url = 'http://songza.com/api/1/station/multi?'

    params = ''
    for scenarioData in data:
        if scenarioData['title'] == scenario:
            for situationData in scenarioData['situations']:
                if situationData['id'] == situation:
                    keys = []
                    for i in range(len(situationData['station_ids'])):
                        keys.append('id')
                    ids = zip(keys, situationData['station_ids'])
                    params = urllib.urlencode(ids)

    data = GetData(url, params)

    for station in data:

        AddStation(station['name'], station['id'], iconImage=station['cover_url'])

    xbmcplugin.endOfDirectory(HANDLE)


def AddStation(name, id, iconImage):
    url = PLUGIN_URL + 'station=%s' % id
    return AddMenuEntry(name, url, False, iconImage)


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


def GetData(url, params=None):
    json = requests.get(url, params=params).json()
    return json


def GetHtml(url, params=None):
    response = requests.get(url, params=params)
    return response.text

args = GetArguments()

if 'play' in args:
    PlayTrack(args['station'][0], args['play'][0])
elif 'station' in args:
    PlayStation(args['station'][0])
elif 'subcategoryUrl' in args:
    ListBrowseStations(urllib.unquote(args['subcategoryUrl'][0]))
elif 'categoryUrl' in args:
    ListBrowseSubcategories(urllib.unquote(args['categoryUrl'][0]))
elif 'situation' in args:
    ListConciergeStations(urllib.unquote(args['scenario'][0]), urllib.unquote(args['situation'][0]))
elif 'scenario' in args:
    ListSituations(urllib.unquote(args['scenario'][0]))
elif 'mode' in args:
    if int(args['mode'][0]) == 1:  # Music Concierge
        ListScenarios()
    #TODO elif int(args['mode'][0]) == 2:  # Popular
    elif int(args['mode'][0]) == 3:  # Browse
        ListBrowseCategories()
else:
    RootMenu()
