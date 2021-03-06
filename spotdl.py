#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from core import metadata
from core import convert
from core import misc
from bs4 import BeautifulSoup
from titlecase import titlecase
from slugify import slugify

import spotipy
import pafy
import urllib.request
import sys
import os
import time


def generate_token():
    new_token = misc.generate_token()
    spotify = spotipy.Spotify(auth=new_token)
    return spotify

def generate_songname(tags):
    """Generate a string of the format '[artist] - [song]' for the given spotify song."""
    raw_song = u'{0} - {1}'.format(tags['artists'][0]['name'], tags['name'])
    return raw_song


def generate_metadata(raw_song):
    """Fetch a song's metadata from Spotify."""
    if misc.is_spotify(raw_song):
        # fetch track information directly if it is spotify link

        spotify = generate_token()
        meta_tags = spotify.track(raw_song)

    else:
        # otherwise search on spotify and fetch information from first result
        try:
            meta_tags = spotify.search(raw_song, limit=1)['tracks']['items'][0]
        except:
            return None
    artist = spotify.artist(meta_tags['artists'][0]['id'])
    album = spotify.album(meta_tags['album']['id'])

    try:
        meta_tags[u'genre'] = titlecase(artist['genres'][0])
    except IndexError:
        meta_tags[u'genre'] = None
    try:
        meta_tags[u'copyright'] = album['copyrights'][0]['text']
    except IndexError:
        meta_tags[u'copyright'] = None
    try:
        meta_tags['isrc']
    except KeyError:
        meta_tags['isrc'] = None

    meta_tags[u'release_date'] = album['release_date']
    meta_tags[u'publisher'] = album['label']
    meta_tags[u'total_tracks'] = album['tracks']['total']

    return meta_tags


def generate_youtube_url(raw_song, tries_remaining=5):
    """Search for the song on YouTube and generate a URL to its video."""
    # prevents an infinite loop but allows for a few retries
    if tries_remaining == 0:
        return

    try:
        meta_tags = generate_metadata(raw_song)
    except spotipy.oauth2.SpotifyOauthError:
        spotify = generate_token()
        meta_tags = generate_metadata(raw_song)

    if meta_tags is None:
        song = raw_song
        search_url = misc.generate_search_url(song, viewsort=False)
    else:
        song = generate_songname(meta_tags)
        search_url = misc.generate_search_url(song, viewsort=True)

    item = urllib.request.urlopen(search_url).read()
    # item = unicode(item, 'utf-8')
    items_parse = BeautifulSoup(item, "html.parser")

    videos = []
    for x in items_parse.find_all('div', {'class': 'yt-lockup-dismissable yt-uix-tile'}):
        # ensure result is not a channel
        if x.find('channel') is not None or 'yt-lockup-channel' in x.parent.attrs['class'] or 'yt-lockup-channel' in x.attrs['class']:
            continue

        # ensure result is not a mix/playlist
        if 'yt-lockup-playlist' in x.parent.attrs['class']:
            continue

        # confirm the video result is not an advertisement
        if x.find('googleads') is not None:
            continue

        y = x.find('div', class_='yt-lockup-content')
        link = y.find('a')['href']
        title = y.find('a')['title']
        try:
            videotime = x.find('span', class_="video-time").get_text()
        except AttributeError:
            return generate_youtube_url(raw_song, tries_remaining - 1)

        youtubedetails = {'link': link, 'title': title, 'videotime': videotime, 'seconds':misc.get_sec(videotime)}
        videos.append(youtubedetails)
        if meta_tags is None:
            break

    if not videos:
        return None

    if args.manual:
        print(song)
        print('')
        print('0. Skip downloading this song')
        # fetch all video links on first page on YouTube
        for i, v in enumerate(videos):
          print(u'{0}. {1} {2} {3}'.format(i+1, v['title'], v['videotime'], "http://youtube.com"+v['link']))
        print('')
        # let user select the song to download
        result = misc.input_link(videos)
        if result is None:
            return None
    else:
        if meta_tags is not None:
            # filter out videos that do not have a similar length to the Spotify song
            duration_tolerance = 10
            max_duration_tolerance = 20
            possible_videos_by_duration = list()

            '''
            start with a reasonable duration_tolerance, and increment duration_tolerance
            until one of the Youtube results falls within the correct duration or
            the duration_tolerance has reached the max_duration_tolerance
            '''
            while len(possible_videos_by_duration) == 0:
                possible_videos_by_duration = list(filter(lambda x: abs(x['seconds'] - (int(meta_tags['duration_ms'])/1000)) <= duration_tolerance, videos))
                duration_tolerance += 1
                if duration_tolerance > max_duration_tolerance:
                    print(meta_tags['name'], 'by', meta_tags['artists'][0]['name'], 'was not found')
                    return None

            result = possible_videos_by_duration[0]
        else:
            # if the metadata could not be acquired, take the first result from Youtube because the proper song length is unknown
            result = videos[0]

    full_link = None
    if result:
        full_link = u'youtube.com{0}'.format(result['link'])

    return full_link


def go_pafy(raw_song):
    """Parse track from YouTube."""
    track_url = generate_youtube_url(raw_song)
    if track_url is None:
        return None
    else:
        return pafy.new(track_url)


def get_youtube_title(content, number=None):
    """Get the YouTube video's title."""
    title = content.title
    if number is None:
        return title
    else:
        return '{0}. {1}'.format(number, title)

def feed_album(album):
    new_token = misc.generate_token()
    spotify = spotipy.Spotify(auth=new_token)
    album_tracks = spotify.album_tracks(album, limit=50, offset=0)
    for tracks in album_tracks['items']:
        print(tracks['name'])
        print(tracks['href'])
        # nth input song
        number = 1
        raw_song = tracks['href']
        raw_song = raw_song.replace('tracks','track').replace('api','open').replace('v1/','')
        print('Fetching album: ' + tracks['name'])
        try:
            grab_single(raw_song, number=number)
            # token expires after 1 hour
            # detect network problems
        except (urllib.request.URLError, TypeError, IOError):
                # wait 0.5 sec to avoid infinite looping
            new_token = misc.generate_token()
            #global spotify
            spotify = spotipy.Spotify(auth=new_token)
            print('network issue')
            time.sleep(0.5)
            continue
        except KeyboardInterrupt:
            misc.grace_quit()
        finally:
            print('')
        number += 1



def feed_playlist(username):
    """Fetch user playlists when using the -u option."""
    playlists = spotify.user_playlists(username)
    print('...printing playlists...')
    links = []
    check = 1

    while True:
        for playlist in playlists['items']:
            # in rare cases, playlists may not be found, so playlists['next']
            # is None. Skip these. Also see Issue #91.
            if playlist['name'] is not None:
                print(u'{0:>5}. {1:<30}  ({2} tracks)'.format(
                    check, playlist['name'],
                    playlist['tracks']['total']))
                links.append(playlist)
                check += 1
        if playlists['next']:
            playlists = spotify.next(playlists)
        else:
            break

    print('Playlists written')
    #playlist = misc.input_link(links)
    for playlist in links:
        write_tracks(playlist)


def write_tracks(playlist):
    results = spotify.user_playlist(
        playlist['owner']['id'], playlist['id'], fields='tracks,next')
    text_file = u'{0}.txt'.format(slugify(playlist['name'], ok='-_()[]{}'))
    print(u'Feeding {0} tracks to {1}'.format(playlist['tracks']['total'], text_file))

    tracks = results['tracks']
    with open(text_file, 'a') as file_out:
        while True:
            for item in tracks['items']:
                track = item['track']
                try:
                    file_out.write(track['external_urls']['spotify'] + '\n')
                except KeyError:
                    print(u'Skipping track {0} by {1} (local only?)'.format(
                        track['name'], track['artists'][0]['name']))
            # 1 page = 50 results
            # check if there are more pages
            if tracks['next']:
                tracks = spotify.next(tracks)
            else:
                break

def update_song_base(file_name, content):
    file_to_check = '{0}{1}'.format(os.path.join(args.folder, file_name.replace('_', ' ')), '.mp3')
    if os.path.isfile(file_to_check):
        return False

def download_song(file_name, content):
    """Download the audio file from YouTube."""
    if args.input_ext == '.webm':
        link = content.getbestaudio(preftype='webm')
    elif args.input_ext == '.m4a':
        link = content.getbestaudio(preftype='m4a')
    else:
        return False

    if link is None:
        return False
    else:
        #Check whether mp3 file already exist
        file_to_check = '{0}{1}'.format(os.path.join(args.folder, file_name.replace('_',' ')), '.mp3')
        print('******')
        print(file_to_check)
        if os.path.isfile(file_to_check):
            return False

        link.download(
            filepath='{0}{1}'.format(os.path.join(args.folder, file_name), args.input_ext))
        return True


def check_exists(music_file, raw_song, islist=True):
    """Check if the input song already exists in the given folder."""
    songs = os.listdir(args.folder)
    for song in songs:
        if song.endswith('.temp'):
            os.remove(os.path.join(args.folder, song))
            continue
        # check if any song with similar name is already present in the given folder
        file_name = misc.sanitize_title(music_file)
        if song.startswith(file_name):
            # check if the already downloaded song has correct metadata
            already_tagged = metadata.compare(os.path.join(args.folder, song), generate_metadata(raw_song))

            # if not, remove it and download again without prompt
            if misc.is_spotify(raw_song) and not already_tagged:
                os.remove(os.path.join(args.folder, song))
                return False

            # do not prompt and skip the current song
            # if already downloaded when using list
            if islist:
                print('Song already exists')
                return True
            # if downloading only single song, prompt to re-download
            else:
                #prompt = input('Song with same name has already been downloaded. '
                               #'Re-download? (y/n): ').lower()
                #if prompt == 'y':
                #    os.remove(os.path.join(args.folder, song))
                os.remove(os.path.join(args.folder, song))
                return False
                #else:
                  #  return True
    return False

def get_song_name(raw_song):
    try:
        meta_tags = generate_metadata(raw_song)
        content = go_pafy(raw_song)
    except (urllib.request.URLError, TypeError, IOError, spotipy.oauth2.SpotifyOauthError):
        spotify = generate_token()
        meta_tags = generate_metadata(raw_song)
    if meta_tags is None:
        songname = content.title
    else:
        songname = generate_songname(meta_tags)
        print('Song -->' + songname)
    file_name = misc.sanitize_title(songname)
    file_name = file_name + ".mp3"
    return filename

def grab_list(text_file):
    """Download all songs from the list."""
    with open(text_file, 'r') as listed:
        lines = (listed.read()).splitlines()
    # ignore blank lines in text_file (if any)
    try:
        lines.remove('')
    except ValueError:
        pass
    print(u'Total songs in list: {0} songs'.format(len(lines)))
    print('')
    # nth input song
    number = 1
    for raw_song in lines:
        try:
            grab_single(raw_song, number=number)
            get_song_name(raw_song)
        # token expires after 1 hour
        except spotipy.oauth2.SpotifyOauthError:
            # refresh token when it expires
            #new_token = misc.generate_token()
            global spotify
            #spotify = spotipy.Spotify(auth=new_token)
            spotify = generate_token()
            grab_single(raw_song, number=number)
        # detect network problems
        except (urllib.request.URLError, TypeError, IOError):
            lines.append(raw_song)
            # remove the downloaded song from .txt
            misc.trim_song(text_file)
            # and append it to the last line in .txt
            with open(text_file, 'a') as myfile:
                myfile.write(raw_song + '\n')
            print('Failed to download song. Will retry after other songs.')
            # wait 0.5 sec to avoid infinite looping
            time.sleep(0.5)
            continue
        except KeyboardInterrupt:
            misc.grace_quit()
        finally:
            print('')
        misc.trim_song(text_file)
        number += 1

    #remove the list file 
    #os.remove(os.path.join(text_file))
    #not anymore, we want them to be synchronized


def grab_playlist(playlist):
    if '/' in playlist:
        if playlist.endswith('/'):
            playlist = playlist[:-1]
        splits = playlist.split('/')
    else:
        splits = playlist.split(':')

    username = splits[-3]
    playlist_id = splits[-1]
    playlists = spotify.user_playlists(username)

    while True:
        for playlist in playlists['items']:
            if not playlist['name'] == None:
                if playlist['id'] == playlist_id:
                    playlists['next'] = None
                    break
        if playlists['next']:
            playlists = spotify.next(playlists)
        else:
            break

    write_tracks(playlist)


def grab_single(raw_song, number=None):
    """Logic behind downloading a song."""
    print('grab single ' + raw_song)
    if number:
        islist = True
    else:
        islist = False
    content = go_pafy(raw_song)
    if content is None:
        return

    # print '[number]. [artist] - [song]' if downloading from list
    # otherwise print '[artist] - [song]'
    print(get_youtube_title(content, number))

    # generate file name of the song to download
    try:
        meta_tags = generate_metadata(raw_song)
    except (urllib.request.URLError, TypeError, IOError, spotipy.oauth2.SpotifyOauthError):
        spotify = generate_token()
        meta_tags = generate_metadata(raw_song)
    if meta_tags is None:
        songname = content.title
    else:
        songname = generate_songname(meta_tags)
        print('Song -->' + songname)
    file_name = misc.sanitize_title(songname)

    if not check_exists(file_name, raw_song, islist=islist):
        if download_song(file_name, content):
            print('')
            input_song = file_name + args.input_ext
            output_song = file_name + args.output_ext
            print(output_song)
            convert.song(input_song, output_song, args.folder,
                         avconv=args.avconv, verbose=args.verbose)
            if not args.input_ext == args.output_ext:
                os.remove(os.path.join(args.folder, input_song))

            if not args.no_metadata:
                metadata.embed(os.path.join(args.folder, output_song), meta_tags)
        else:
            print('No audio streams available or song already downloaded')


class TestArgs(object):
    manual = False
    input_ext = '.m4a'
    output_ext = '.mp3'

# token is mandatory when using Spotify's API
# https://developer.spotify.com/news-stories/2017/01/27/removing-unauthenticated-calls-to-the-web-api/
token = misc.generate_token()
spotify = spotipy.Spotify(auth=token)

print('main')

if __name__ == '__main__':
    os.chdir(sys.path[0])
    args = misc.get_arguments()

    print(args)

    misc.filter_path(args.folder)

    if args.song:
        print('song')
        grab_single(raw_song=args.song)
    elif args.list:
        grab_list(text_file=args.list)
    elif args.playlist:
        grab_playlist(playlist=args.playlist)
    elif args.username:
        feed_playlist(username=args.username)

    elif args.album:
        feed_album(album=args.album)

    #renaming song names
    for filename in os.listdir(args.folder):
        if filename != '.DS_Store':

            os.rename(args.folder + '/' +filename, args.folder + '/' + filename.replace('_',' '))
else:
    misc.filter_path('Music')
    args = TestArgs()
