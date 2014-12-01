# -*- coding: utf-8 -*-

#   This file is part of periscope.
#   Copyright (c) 2008-2011 Patrick Dessalle <patrick@dessalle.be>
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    periscope is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with periscope; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os, struct, xmlrpclib, commands, gzip, traceback, logging, re, ConfigParser
import socket # For timeout purposes

import SubtitleDatabase

log = logging.getLogger(__name__)

OS_LANGS ={ "en": "eng", 
            "fr" : "fre", 
            "hu": "hun", 
            "cs": "cze", 
            "pl" : "pol", 
            "sk" : "slo", 
            "pt" : "por", 
            "pt-br" : "pob", 
            "es" : "spa", 
            "el" : "ell", 
            "ar":"ara",
            'sq':'alb',
            "hy":"arm",
            "ay":"ass",
            "bs":"bos",
            "bg":"bul",
            "ca":"cat",
            "zh":"chi",
            "hr":"hrv",
            "da":"dan",
            "nl":"dut",
            "eo":"epo",
            "et":"est",
            "fi":"fin",
            "gl":"glg",
            "ka":"geo",
            "de":"ger",
            "he":"heb",
            "hi":"hin",
            "is":"ice",
            "id":"ind",
            "it":"ita",
            "ja":"jpn",
            "kk":"kaz",
            "ko":"kor",
            "lv":"lav",
            "lt":"lit",
            "lb":"ltz",
            "mk":"mac",
            "ms":"may",
            "no":"nor",
            "oc":"oci",
            "fa":"per",
            "ro":"rum",
            "ru":"rus",
            "sr":"scc",
            "sl":"slv",
            "sv":"swe",
            "th":"tha",
            "tr":"tur",
            "uk":"ukr",
            "vi":"vie"}

class OpenSubtitles(SubtitleDatabase.SubtitleDB):
    url = "http://www.opensubtitles.org/"
    site_name = "OpenSubtitles"
    
    def __init__(self, config, cache_folder_path):
        super(OpenSubtitles, self).__init__(OS_LANGS)
        self.server_url = 'http://api.opensubtitles.org/xml-rpc'
        self.revertlangs = dict(map(lambda item: (item[1],item[0]), self.langs.items()))
        self.tvshowRegex = re.compile('(?P<show>.*)S(?P<season>[0-9]{2})E(?P<episode>[0-9]{2}).?(?P<data>[a-zA-Z].*)?.(?P<quality>BDRIP.*|BLURAY.*|HDTV.*|420p.HDTV.*|720p.HDTV.*|720p.WEB-DL.*|720p.BLURAY.*|1080p.HDTV.*|1080p.WEB-DL.*|1080p.BLURAY.*|1080i.HDTV)-(?P<group>.*)', re.IGNORECASE)
        self.movieRegex = re.compile('(?P<movie>.*)[\_\.|\[|\(| ]{1}(?P<year>(?:(?:19|20)[0-9]{2})).(?P<dados>.*)-(?P<teams>.*)', re.IGNORECASE)		
        try:
            self.user = config.get("Opensubtitles","user")
            self.password = config.get("Opensubtitles","pass")
            self.tvshowhash = config.get("Opensubtitles","tvshowhash")			
            self.moviehash = config.get("Opensubtitles","moviehash")				
			
        except ConfigParser.NoSectionError:
            config.add_section("Opensubtitles")
            config.set("Opensubtitles", "user", "")
            config.set("Opensubtitles", "pass", "")
            config.set("Opensubtitles", "tvshowhash", "no")
            config.set("Opensubtitles", "moviehash", "no")			
            config_file = os.path.join(cache_folder_path, "config")
            configfile = open(config_file, "w")
            config.write(configfile)
            configfile.close()
            pass

    def process(self, filepath, langs):
        ''' main method to call on the plugin, pass the filename and the wished 
        languages and it will query OpenSubtitles.org '''
        if os.path.isfile(filepath):
            filename = self.getFileName(filepath)
            filename = filename.replace("WEB-DL", "WEBDL")
            if filename.find("-") < 0: filename+="-NOGROUP"
            filename = filename.replace("WEBDL", "WEB-DL")			
            matches_tvshow = self.tvshowRegex.match(filename)
            matches_movie = self.movieRegex.match(filename)	
            if matches_tvshow:			
                if self.tvshowhash == "no":
                    log.debug(" Not using hash for tv-show")
                    fname = self.getFileName(filepath)				
                    (tvshow, season, episode, epname, dados, teams) = matches_tvshow.groups()
                    log.debug(" Matched tv-show")
                    log.debug(matches_tvshow.groups())					
                    tvshow = tvshow.replace(".US.", " ").strip()
                    tvshow = tvshow.replace(".", " ").strip()
                    tvshow = tvshow.replace("_", " ").strip()
                    return self.query(movie=None, myear=None, mteams=None, mdados=None ,tvshow=tvshow, season=season, episode=episode, epname=epname, teams=teams, dados=dados, moviehash=None, langs=langs, bytesize=None, filename=fname)
                else:
                    log.debug(" Using hash for tv-show")			
                    filehash = self.hashFile(filepath)
                    log.debug(filehash)
                    size = os.path.getsize(filepath)
                    fname = self.getFileName(filepath)
                    return self.query(movie=None, myear=None, mteams=None, mdados=None ,tvshow=None, season=None, episode=None, epname=None, teams=None, dados=None, moviehash=filehash, langs=langs, bytesize=size, filename=fname)
            elif matches_movie:	
                if self.moviehash == "no":
                    log.debug(" Not using hash for movies")
                    fname = self.getFileName(filepath)
                    (movie, myear, mdados, mteams) = matches_movie.groups()
                    log.debug(" Matched movie")
                    log.debug(matches_movie.groups())
                    movie = movie.replace(".", " ").strip()
                    movie = movie.replace("_", " ").strip()
                    return self.query(movie=movie, myear=myear, mteams=mteams, mdados=mdados, tvshow=None, season=None, episode=None, epname=None, teams=None, dados=None, moviehash=None, langs=langs, bytesize=None, filename=fname)				
            else:
                log.debug(" Using hash for movie")			
                filehash = self.hashFile(filepath)
                log.debug(filehash)
                size = os.path.getsize(filepath)
                fname = self.getFileName(filepath)
                return self.query(movie=None, myear=None, mteams=None, mdados=None, tvshow=None, season=None, episode=None, epname=None, teams=None, dados=None, moviehash=filehash, langs=langs, bytesize=size, filename=fname)			
        else:
            fname = self.getFileName(filepath)
            return self.query(langs=langs, filename=fname)
        
    def createFile(self, subtitle):
        '''pass the URL of the sub and the file it matches, will unzip it
        and return the path to the created file'''
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtbasefilename = videofilename.rsplit(".", 1)[0]
        self.downloadFile(suburl, srtbasefilename + ".srt.gz")
        f = gzip.open(srtbasefilename+".srt.gz")
        dump = open(srtbasefilename+".srt", "wb")
        dump.write(f.read())
        dump.close()
        f.close()
        os.remove(srtbasefilename+".srt.gz")
        return srtbasefilename+".srt"

    def query(self, filename=None, imdbID=None, moviehash=None, bytesize=None, langs=None, tvshow=None, season=None, episode=None, epname=None, teams=None, dados=None, movie=None, myear=None, mteams=None, mdados=None):
        ''' Makes a query on opensubtitles and returns info about found subtitles.
            Note: if using moviehash, bytesize is required.    '''
        log.debug('query')
        #Prepare the search
        search = {}
        sublinks = []
        if filename: fname = filename
        if tvshow: search['query'] = tvshow.lower().replace('the','')
        if season: search['season'] = season
        if episode: search['episode'] = episode
        #if movie: search['MovieName'] = movie - DONT'T WORK
        if movie: search['query'] = movie.lower().replace('the','')	
        if myear: search['MovieYear'] = myear
        if moviehash: search['moviehash'] = moviehash
        if imdbID: search['imdbid'] = imdbID
        if bytesize: search['moviebytesize'] = str(bytesize)
        if langs: search['sublanguageid'] = ",".join([self.getLanguage(lang) for lang in langs])
        log.debug(search)
        if len(search) == 0:
            log.debug("No search term, we'll use the filename")
            # Let's try to guess what to search:
            guessed_data = self.guessFileData(filename)
            search['query'] = guessed_data['name']
            log.debug(search['query'])
            
        #Login
        self.server = xmlrpclib.Server(self.server_url)
        socket.setdefaulttimeout(10)
        if not self.user or self.password == "":
            username = None
            password = None
        else :
            username = self.user
            password = self.password
        try:
            log_result = self.server.LogIn(username,password,"eng","periscope")
            log.debug(log_result)
            token = log_result["token"]
        except Exception:
            log.error("Open subtitles could not be contacted for login")
            token = None
            socket.setdefaulttimeout(None)
            return []
        if not token:
            log.error("Open subtitles did not return a token after logging in.")
            return []            
            
        # Search
        self.filename = filename #Used to order the results
        sublinks += self.get_results(token, search, teams, dados, mteams, mdados, fname, season, episode)

        # Logout
        try:
            self.server.LogOut(token)
        except:
            log.error("Open subtitles could not be contacted for logout")
        socket.setdefaulttimeout(None)
        return sublinks
        
        
    def get_results(self, token, search, teams, dados, mteams, mdados, fname, season, episode):
        log.debug("query: token='%s', search='%s'" % (token, search))
        try:
            if search:
                results = self.server.SearchSubtitles(token, [search])
        except Exception, e:
            log.error("Could not query the server OpenSubtitles")
            log.debug(e)
            return []
        log.debug("Result: %s" %str(results))

        sublinks = []
        if results['data']:
            log.debug(results['data'])
            # OpenSubtitles hash function is not robust ... We'll use the MovieReleaseName to help us select the best candidate
            for r in sorted(results['data'], self.sort_by_moviereleasename):
                # Only added if the MovieReleaseName matches the file
                result = {}
                result["release"] = r['SubFileName']
                result["link"] = r['SubDownloadLink']
                result["page"] = r['SubDownloadLink']
                result["lang"] = self.getLG(r['SubLanguageID'])
                result["usernick"] = r['UserNickName']				
                if search.has_key("season") or search.has_key("MovieYear") :
                    if search.has_key("MovieYear"): 
                        log.debug(" Result is a movie")
                        matches_movie = self.movieRegex.match(r["MovieReleaseName"])
                        if matches_movie: # It looks like a movie
                            log.debug(" Movie matched using REGEX");	
                            (movie_r, myear_r, mdados_r, mteams_r) = matches_movie.groups()	
                            log.debug(matches_movie.groups());							
                            if r["MovieReleaseName"] == fname:					
                                log.info(" Release filename matched. Release: " + r["MovieReleaseName"] + " Filename: " + fname)
                                sublinks.append(result)
                            elif mteams.lower() == mteams_r.lower():
                                log.info(" Movie group matched. Subtitle: " + mteams + " Filename: " + mteams_r)
                                sublinks.append(result)
                            elif mdados.lower().find("web-dl") >= 0 and r["MovieReleaseName"].lower().find("web-dl") >= 0 :	
                                log.info(" Movie release has WEB-DL on it. Release: " + r["MovieReleaseName"])
                                sublinks.append(result)
                            elif (mdados.lower().find("bluray") >= 0 or mdados.lower().find("bdrip") >= 0 or mdados.lower().find("brrip") >= 0) and (r["MovieReleaseName"].lower().find("bluray") >= 0 or r["MovieReleaseName"].lower().find("bdrip") >= 0 or r["MovieReleaseName"].lower().find("brrip") >= 0):	
                                log.info(" Movie release has BLURAY/BDRIP/BRRIP on it. Release: " + r["MovieReleaseName"])
                                sublinks.append(result)								
                            #elif mdados.lower().find("bluray") >= 0 and r["MovieReleaseName"].lower().find("bluray") >= 0:	
                            #    log.info(" Movie release has BLURAY on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)
                            #elif mdados.lower().find("bdrip") >= 0 and r["MovieReleaseName"].lower().find("bdrip") >= 0:	
                            #    log.info(" Movie release has BDRIP on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)									
                            #elif mdados.lower().find("brrip") >= 0 and r["MovieReleaseName"].lower().find("brrip") >= 0:	
                            #    log.info(" Movie release has BRRIP on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)									
                            else:
                                log.info(" Movie didnt matched. Release: " + r["MovieReleaseName"] + " Subtitle: " + r['SubFileName'])	
                        else: # It looks like a movie, but didnt matched using REGEX							
                            log.debug(" Movie didnt matched using REGEX");					
                            if r["MovieReleaseName"].lower().find(mteams.lower()) >= 0 :	
                                log.info(" Movie release has group on it. Release: " + r["MovieReleaseName"])
                                sublinks.append(result)
                            elif mdados.lower().find("web-dl") >= 0 and r["MovieReleaseName"].lower().find("web-dl") >= 0 :	
                                log.info(" Movie release has WEB-DL on it. Release: " + r["MovieReleaseName"])
                                sublinks.append(result)
                            elif (mdados.lower().find("bluray") >= 0 or mdados.lower().find("bdrip") >= 0 or mdados.lower().find("brrip") >= 0) and (r["MovieReleaseName"].lower().find("bluray") >= 0 or r["MovieReleaseName"].lower().find("bdrip") >= 0 or r["MovieReleaseName"].lower().find("brrip") >= 0):	
                                log.info(" Movie release has BLURAY/BRRIP/BDRIP on it. Release: " + r["MovieReleaseName"])
                                sublinks.append(result)									
                            #elif mdados.lower().find("bluray") >= 0 and r["MovieReleaseName"].lower().find("bluray") >= 0:	
                            #    log.info(" Movie release has BLURAY on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)
                            #elif mdados.lower().find("bdrip") >= 0 and r["MovieReleaseName"].lower().find("bdrip") >= 0:	
                            #    log.info(" Movie release has BDRIP on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)									
                            #elif mdados.lower().find("brrip") >= 0 and r["MovieReleaseName"].lower().find("brrip") >= 0:	
                            #    log.info(" Movie release has BRRIP on it. Release: " + r["MovieReleaseName"])
                            #    sublinks.append(result)									
                            else:							
                                log.info(" Movie release didnt matched. Release: "  + r["MovieReleaseName"] + " Subtitle: " + r['SubFileName'])
                    if search.has_key("season"):
                        log.debug(" Result is a tv-show")
                        matches_tvshow = self.tvshowRegex.match(r["MovieReleaseName"])
                        if matches_tvshow: # It looks like a tv show
                            log.debug(" Tv-show matched using REGEX");
                            (tvshow_r, season_r, episode_r, epname_r, dados_r, teams_r) = matches_tvshow.groups()
                            log.debug(matches_tvshow.groups());	
                            if teams.lower() == teams_r.lower() and r['UserNickName'] in ("noriegaRJ","AlbustigriS") and season.lower() == season_r.lower()  and episode.lower() == episode_r.lower():
                                log.info(" Tv-show group matched. Filename: " + teams + " Subtitle: " + teams_r + " User: " + r['UserNickName'])
                                sublinks.append(result)
                            elif dados.lower().find("web-dl") >= 0 and dados_r.lower().find("web-dl") >= 0 and r['UserNickName'] in ("noriegaRJ","AlbustigriS") and season.lower() == season_r.lower()  and episode.lower() == episode_r.lower():	
                                log.info(" Tv-show release has WEB-DL on it. Release: " + r["MovieReleaseName"] + " User: " + r['UserNickName'])
                                sublinks.append(result)								
                            else: 
                                log.info(" Group dont match. Filename: " + teams + " Subtitle: " + teams_r )							
                        else:  # It looks like a tv-show, but didnt matched using REGEX
                            log.debug(" Tv-show Didnt matched using REGEX");
                            log.debug(" MovieReleaseName: " + r["MovieReleaseName"].lower())
                            log.debug(" Subtitle filename: " + r['SubFileName'])
                            #log.debug(r["MovieReleaseName"].lower() + ' s'+season+'e'+episode)
                            if r["MovieReleaseName"].lower().find(teams.lower()) >= 0 and r['UserNickName'] in ("noriegaRJ","AlbustigriS") and r["MovieReleaseName"].lower().find('s'+season+'e'+episode) > 0 :	
                                log.info(" Tv-show release has group on it. Release: " + r["MovieReleaseName"] + " User: " + r['UserNickName'])
                                sublinks.append(result)
                            elif dados.lower().find("web-dl") >= 0 and r["MovieReleaseName"].lower().find("web-dl") >= 0 and r['UserNickName'] in ("noriegaRJ","AlbustigriS") and r['SubFileName'].lower().find('s'+season+'e'+episode) > 0 :	
                                log.info(" Tv-show release has WEB-DL on it. Release: " + r["MovieReleaseName"] + " User: " + r['UserNickName'])
                                sublinks.append(result)							
                            else:							
                                log.info(" Tv-show release didnt matched. Release: "  + r["MovieReleaseName"])
                else :
                    sublinks.append(result)
        return sublinks

    def sort_by_moviereleasename(self, x, y):
        ''' sorts based on the movierelease name tag. More matching, returns 1'''
        #TODO add also support for subtitles release
        xmatch = x['MovieReleaseName'] and (x['MovieReleaseName'].find(self.filename)>-1 or self.filename.find(x['MovieReleaseName'])>-1)
        ymatch = y['MovieReleaseName'] and (y['MovieReleaseName'].find(self.filename)>-1 or self.filename.find(y['MovieReleaseName'])>-1)
        #print "analyzing %s and %s = %s and %s" %(x['MovieReleaseName'], y['MovieReleaseName'], xmatch, ymatch)
        if xmatch and ymatch:
            if x['MovieReleaseName'] == self.filename or x['MovieReleaseName'].startswith(self.filename) :
                return -1
            return 0
        if not xmatch and not ymatch:
            return 0
        if xmatch and not ymatch:
            return -1
        if not xmatch and ymatch:
            return 1
        return 0
