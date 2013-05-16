# -*- coding: utf-8 -*-

#    This file is part of periscope.
#
#     periscope is free software; you can redistribute it and/or modify
#     it under the terms of the GNU Lesser General Public License as published by
#     the Free Software Foundation; either version 2 of the License, or
#     (at your option) any later version.
#
#     periscope is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU Lesser General Public License for more details.
#
#     You should have received a copy of the GNU Lesser General Public License
#     along with periscope; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA    02110-1301    USA
#
#    Original version based on XBMC Legendas.tv plugin: 
#    https://github.com/amet/script.xbmc.subtitles/blob/eden/script.xbmc.subtitles/resources/lib/services/LegendasTV/service.py
#
#    Initial version coded by Gastao Bandeira
#    Bug fix and minor changes by Rafael Torres
#    Improved search by Fernando G
#    TO DO: improved search to include PACKs and double repisodes (S01E01E02) and multi episode inside .RAR (script get the first match and file match not always works)

import xml.dom.minidom
import traceback
import hashlib
import StringIO
import zipfile
import shutil
import ConfigParser
import random

import cookielib, urllib2, urllib, sys, re, os, webbrowser, time, unicodedata, logging
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
from htmlentitydefs import name2codepoint as n2cp

#from utilities import log

import SubtitleDatabase
import subprocess

log = logging.getLogger(__name__)

class LegendasTV(SubtitleDatabase.SubtitleDB):
    url = "http://legendas.tv"
    site_name = "LegendasTV"
    user_agent = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.64 Safari/537.31"

    def __init__(self, config, cache_folder_path ):
        super(LegendasTV, self).__init__(None)
        self.tvshowRegex = re.compile('(?P<show>.*)S(?P<season>[0-9]{2})E(?P<episode>[0-9]{2}).(?P<teams>.*)', re.IGNORECASE)
        self.tvshowRegex2 = re.compile('(?P<show>.*).(?P<season>[0-9]{1,2})x(?P<episode>[0-9]{1,2}).(?P<teams>.*)', re.IGNORECASE)
        self.movieRegex = re.compile('(?P<movie>.*)[\_\.|\[|\(| ]{1}(?P<year>(?:(?:19|20)[0-9]{2}))(?P<teams>.*)', re.IGNORECASE)
        self.user = None
        self.password = None
        self.unrar = None
        self.sub_ext = None
        try:
            self.user = config.get("LegendasTV","user")
            self.password = config.get("LegendasTV","pass")
            self.unrar = config.get("LegendasTV","unrarpath")
            self.sub_ext = config.get("LegendasTV","supportedSubtitleExtensions")
        except ConfigParser.NoSectionError:
            config.add_section("LegendasTV")
            config.set("LegendasTV", "user", "")
            config.set("LegendasTV", "pass", "")
            config.set("LegendasTV", "unrarpath", "")
            config.set("LegendasTV", "supportedSubtitleExtensions", "")
            config_file = os.path.join(cache_folder_path, "config")
            configfile = open(config_file, "w")
            config.write(configfile)
            configfile.close()
            pass

    def process(self, filepath, langs):
        ''' main method to call on the plugin, pass the filename and the wished
        languages and it will query the subtitles source '''
        if not self.user or self.user == "":
            log.error("LegendasTV requires a personnal username/password. Set one up in your ~/.config/periscope/config file")
            return []
        if not self.unrar or self.unrar == "":
            log.error("LegendasTV requires Unrar. Select the folder and executable of your unrar in your ~/.config/periscope/config file")
            return []    		
        arquivo = self.getFileName(filepath)
        dados = {}
        dados = self.guessFileData(arquivo)
        log.debug("Dados: " + str(dados))
        if dados['type'] == 'tvshow':
            subtitles = self.LegendasTVSeries(filepath,dados['name'], str(dados['season']), str(dados['episode']), str(dados['teams']), langs)
            #logging.info("Found " + str(len(subtitles)) + " results: " + str(subtitles))
            log.debug("Subtitles: " + str(subtitles))
        elif(dados['type'] == 'movie'):
            subtitles =  self.LegendasTVMovies(filepath,dados['name'],dados['year'],langs)
        else:
            subtitles =  self.LegendasTVMovies(filepath,dados['name'],'',langs)
        return subtitles

    def getFileName(self, filepath):
        filename = os.path.basename(filepath)
        if filename.endswith(('.avi', '.wmv', '.mov', '.mp4', '.mpeg', '.mpg', '.mkv')):
            fname = filename.rsplit('.', 1)[0]
        else:
            fname = filename
        return fname

    def guessFileData(self, filename):
        filename = unicode(self.getFileName(filename).lower()).replace("web-dl","webdl").replace("web.dl","webdl").replace("web dl","webdl")
        log.debug(filename)
        matches_tvshow = self.tvshowRegex.match(filename)
        if matches_tvshow: # It looks like a tv show
            log.debug("Utilizado Regex1")
            (tvshow, season, episode, teams) = matches_tvshow.groups()
            tvshow = tvshow.replace(".", " ").strip()
            tvshow = tvshow.replace("_", " ").strip()
            teams = teams.split('.')
            if len(teams) ==1:
                teams = teams[0].split('-')
            return {'type' : 'tvshow', 'name' : tvshow.strip(), 'season' : int(season), 'episode' : int(episode), 'teams' : teams}
        else:
            matches_tvshow = self.tvshowRegex2.match(filename)
            if matches_tvshow:
                log.debug("Utilizado Regex2")			
                (tvshow, season, episode, teams) = matches_tvshow.groups()
                tvshow = tvshow.replace(".", " ").strip()
                tvshow = tvshow.replace("_", " ").strip()
                teams = teams.split('.')
                if len(teams) ==1:
                    teams = teams[0].split('_')
                return {'type' : 'tvshow', 'name' : tvshow.strip(), 'season' : int(season), 'episode' : int(episode), 'teams' : teams}
            else:
                matches_movie = self.movieRegex.match(filename)
                if matches_movie:
                    (movie, year, teams) = matches_movie.groups()
                    movie = movie.replace(".", " ").strip()
                    movie = movie.replace("_", " ").strip()
                    teams = teams.split('.')
                    if len(teams) ==1:
                        teams = teams[0].split('_')
                    part = None
                    if "cd1" in teams :
                            teams.remove('cd1')
                            part = 1
                    if "cd2" in teams :
                            teams.remove('cd2')
                            part = 2
                    return {'type' : 'movie', 'name' : movie.strip(), 'year' : year, 'teams' : teams, 'part' : part}
                else:
                    return {'type' : 'unknown', 'name' : filename, 'teams' : [] }


    def LegendasTVLogin(self):
        '''Function for login on LegendasTV using username and password from config file'''
        cj = cookielib.MozillaCookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        opener.addheaders = [('User-agent', ('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; .NET CLR 1.1.4322)'))]
        urllib2.install_opener(opener)
        username = self.user
        password = self.password
        login_data = urllib.urlencode({'txtLogin':username,'txtSenha':password})
		
        try:
            request = urllib2.Request(self.url+'/login_verificar.php',login_data)
            response = urllib2.urlopen(request).read()
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason'):
                logging.info("Cant login to LegendasTV. Error: " + str(e.code) + " " +str(e.reason))
        #else:
                #logging.info("Logged on LegendasTV")
	

    def createFile(self, subtitle):
        '''pass the ID of the sub and the file it matches, will unzip it
        and return the path to the created file'''
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtfilename = videofilename.rsplit(".", 1)[0] + '.srt'
        if not self.downloadFile(suburl, srtfilename) == False:
            return srtfilename
        else:
            return False

    def extractFile(self,fname,extract_path,extractedFiles=[]):
        ''' Uncompress the subtitle '''
        if fname in extractedFiles:
            return
        if zipfile.is_zipfile(fname):
            log.debug("Unzipping file " + fname)
            zf = zipfile.ZipFile(fname, "r")
            zf.extractall(extract_path)
            zf.close()
        elif fname.endswith('.rar'):
            try:
                '''Try to use unrar from folder in config file'''
                log.debug("Extracting file " + fname)
                subprocess.call([self.unrar, 'e','-y','-inul',fname, extract_path])
            except OSError as e:
                log.error("OSError [%d]: %s at %s" % (e.errno, e.strerror, e.filename))
            except:
                log.error("General error:" + str(sys.exc_info()[0]))
        else:
            raise Exception("Unknown file format: " + fname)
        
        extractedFiles.append(fname)    

        fs_encoding = sys.getfilesystemencoding()
        for root, dirs, files in os.walk(extract_path.encode(fs_encoding), topdown=False):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".zip",".rar"]:
                    self.extractFile(os.path.join(root, f),extract_path,extractedFiles)

    def downloadFile(self, url, srtfilename):
        ''' Downloads the given url to the given filename '''
        subtitle = ""
		#Added the random number so two tvshow files from the same season/episode but with releases/quality different can be downloaded
        extract_path = os.path.join(srtfilename.replace(self.getFileName(srtfilename),''), str(url)+"-"+str(random.randint(1, 99999)))
        
        try:
            url_request = self.url+'/info.php?d='+url+'&c=1'
            request =  urllib2.Request(url_request)
            response = urllib2.urlopen(request)
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason'):
                logging.info("Cant download file from LegendasTV. Error: " + str(e.code) + " " +str(e.reason))
            return False
        else:			
            ltv_sub = response.read()			
		
        os.makedirs(extract_path)
        fname = os.path.join(extract_path,str(url))
        if response.info().get('Content-Type').__contains__('rar'):
            fname += '.rar'
        else:
            fname += '.zip'
        f = open(fname,'wb')
        f.write(ltv_sub)
        f.close()

        self.extractFile(fname,extract_path)

        legendas_tmp = []
        fs_encoding = sys.getfilesystemencoding()
        for root, dirs, files in os.walk(extract_path.encode(fs_encoding), topdown=False):
            for file in files:
                dirfile = os.path.join(root, file)
                ext = os.path.splitext(dirfile)[1][1:].lower()
                log.debug("file [%s] extension[%s]" % (file,ext))
                if ext in self.sub_ext:
                    log.debug("adding " + dirfile)
                    legendas_tmp.append(dirfile)

        if len(legendas_tmp) == 0:
            shutil.rmtree(extract_path)
            raise Exception('Could not find any subtitle')
        
        '''Verify the best subtitle in case of a pack for multiples releases'''
        legenda_retorno = self.CompareSubtitle(srtfilename,legendas_tmp)
        if legenda_retorno == '':
            logging.info("No subtitle matched")
            shutil.rmtree(extract_path)
            srtfilename = ''
            return False
        else:
            log.debug("Renaming [%s] to [%s] " % (os.path.join(extract_path,legenda_retorno),srtfilename))
            shutil.move(os.path.join(extract_path,legenda_retorno),srtfilename)
            shutil.rmtree(extract_path)		

    def CompareSubtitle(self,releaseFile,subtitleList):
        '''Verify the best subtitle in case of a pack for multiples releases'''
        nameSplit = releaseFile.rsplit(".", 1)[0].replace('.',' ').replace('_',' ').replace('-',' ').replace("'", "").split()
        releasevideo = nameSplit[-1]
        log.debug(releasevideo)
        if any("HDTV" in s for s in nameSplit):
            resolutionvideo = "HDTV"
        if any("720p" in s for s in nameSplit):
            resolutionvideo = "720p"
        if any("1080p" in s for s in nameSplit):
            resolutionvideo = "1080p" 
        logging.info("Subtitle: " + str(self.getFileName(releaseFile).rsplit(".", 1)[0]) + " Resolution: "+ str(resolutionvideo) + " Team: " + str(releasevideo))
        bestMatch = ''
        FirstMatch = ''
        SecondMatch = ''
        FileMatch = ''		
        MatchMode = ''
        for subtitle in subtitleList:
            nameSplitTemp = self.getFileName(subtitle).rsplit(".", 1)[0].replace('.',' ').replace('_',' ').replace('-',' ').replace("'", "").split()
            releasesrt = nameSplitTemp[-1]
            log.debug(releasesrt)
            if any("HDTV" in s for s in nameSplitTemp):
                resolutionsrt = "HDTV"
            if any("420p" in s for s in nameSplitTemp):
                resolutionsrt = "420p"				
            if any("720p" in s for s in nameSplitTemp):
                resolutionsrt = "720p"
            if any("1080p" in s for s in nameSplitTemp):
                resolutionsrt = "1080p"
            if self.getFileName(releaseFile).rsplit(".", 1)[0] == self.getFileName(subtitle).rsplit(".", 1)[0].replace("WEB.DL","WEB-DL"):
                logging.info("File matched: " + str(self.getFileName(subtitle).rsplit(".", 1)[0]))
                FileMatch = str(self.getFileName(subtitle))
            else:
                # If matched using filename, dont match by Team and Resolution
                if len(FileMatch) < 1:			
                    if releasevideo == releasesrt:
                        log.debug("Team matched: " + str(self.getFileName(subtitle)))
                        if resolutionvideo == resolutionsrt:	
                            #FirstMatch = Team AND resolution must be equal
                            logging.info("Resolution: Yes and Team: No - " + str(self.getFileName(subtitle)))
                            FirstMatch = self.getFileName(subtitle)
                        else:
                            #SecondMatch = only team must be equal (some WEB-DL are postest only with resolution 720p )			
                            logging.info("Resolution: No and Team: Yes - " + str(self.getFileName(subtitle)))
                            SecondMatch = self.getFileName(subtitle)
                    else:
                        logging.info("Resolution: No and Team: No - " + str(self.getFileName(subtitle)))
        if len(FileMatch)+len(FirstMatch)+len(SecondMatch) > 1:
            logging.info("FileMatch: " + str(FileMatch) + " FirstMatch: " + str(FirstMatch) + " SecondMatch: " + str(SecondMatch)) 
        if len(FileMatch) > 1:  
			bestMatch = FileMatch		
			MatchMode = "File"
        else:
			if len(FirstMatch) > 1:
		 		bestMatch = FirstMatch
		 		MatchMode = "Team + Resolution"
			else:	
		 		bestMatch = SecondMatch	
		 		MatchMode = "Team (resolution promoted)"
        if len(bestMatch) > 1:	
			logging.info("****************************************************************************************")			
			logging.info("Match mode: " + str(MatchMode)  + ". Subtitle file choosen: " + str(bestMatch))			
			logging.info("****************************************************************************************")
			program_name = "curl"
			arguments = ["-s", "-k", "https://www.notifymyandroid.com/publicapi/notify", "-d", "apikey=d1d0d586fe7f6fadfda8df4c4e74b9c94f2a4f0de4681daf", "-d", "application=Periscope", "-d", "event=Legenda encontrada:", "-d", "description=" + str(bestMatch)]
			command = [program_name]
			command.extend(arguments)
			output = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()[0]
			print output
        return bestMatch

    def LegendasTVMovies(self, file_original_path, title, year, langs):

        log.debug('movie')

        self.LegendasTVLogin()

        # Initiating variables and languages.
        subtitles, sub1 = [], []

        if len(langs) > 1:
            langCode = '99'
        else:
            if langs[0] == 'pt-br':
                langCode = '1'
            if langs[0] == 'pt':
                langCode = '10'
            if langs[0] == 'es':
                langCode = '3'
            
       
        log.debug('Search using file name as release with max of 50 characters')
        # Encodes the first search string using the original movie title, and download it.
        search_string = self.getFileName(file_original_path)[:50]
        search_dict = {'txtLegenda':search_string,'selTipo':'1','int_idioma':langCode}
        search_data = urllib.urlencode(search_dict)
        response = self.SearchLegendasTVSeries(search_data)
		
        # If no subtitles with the original name are found, try the parsed title.
        if response.__contains__('Nenhuma legenda foi encontrada') and search_string != title:
            log.debug('No subtitles found using the original file name, using title instead.')
            search_string = self.CleanLTVTitle(title)
            if len(search_string) < 3: search_string = search_string + year
            search_dict = {'txtLegenda':search_string,'selTipo':'1','int_idioma':langCode}
            search_data = urllib.urlencode(search_dict)
            response = self.SearchLegendasTVSeries(search_data)

        # Retrieves the number of pages.
        pages = re.findall("<a class=\"paginacao\" href=",response)
        if pages: pages = len(pages)+1
        else: pages = 1

        # Download all pages content.
        for x in range(pages):
            if x:
                html = urllib2.urlopen(self.url+'/index.php?opcao=buscarlegenda&pagina='+str(x+1)).read()
                response = response + self.to_unicode_or_bust(html)

        # Parse all content to BeautifulSoup
        soup = BeautifulSoup(response)
        td_results =  soup.findAll('td',{'id':'conteudodest'})
        for td in td_results:
            span_results = td.findAll('span')
            for span in span_results:
                if span.attrs == [('class', 'brls')]:
                    continue
                td = span.find('td',{'class':'mais'})

                # Release name of the subtitle file.
                release = self.Uconvert(td.parent.parent.find('span',{'class':'brls'}).contents[0])

                # This is the download ID for the subtitle.
                download_id = re.search('[a-z0-9]{32}',td.parent.parent.attrs[1][1]).group(0)

                # Find the language of the subtitle extracting it from a image name,
                # and convert it to the OpenSubtitles format.
                ltv_lang = re.findall("images/flag_([^.]*).gif",span.findAll('td')[4].contents[0].attrs[0][1])

                if ltv_lang: ltv_lang = ltv_lang[0]
                if ltv_lang == "br": ltv_lang = "pt-br"
                if ltv_lang == "us": ltv_lang = "en"
                if ltv_lang == "pt": ltv_lang = "pt"
                if ltv_lang == "es": ltv_lang = "es"

                sub1.append( { "release" : release,"lang" : ltv_lang, "link" : download_id, "page" : self.url} )

        return sub1
		
    def SearchLegendasTVSeries(self,search_data):
        try:
            request = urllib2.Request(self.url+'/index.php?opcao=buscarlegenda',search_data)
            response = self.to_unicode_or_bust(urllib2.urlopen(request).read())
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason'):
                logging.info("Cant access LegendasTV. Error: " + str(e.code) + " " +str(e.reason))
            sub1.extend(PartialSubtitles)
        return response

    def LegendasTVSeries(self,file_original_path,tvshow, season, episode, teams, langs):

        self.LegendasTVLogin()

    # Initiating variables and languages.
        subtitles, sub1, sub2, sub3, PartialSubtitles = [], [], [], [], []

        if len(langs) > 1:
            langCode = '99'
        else:
            if langs[0] == 'pt-br':
                langCode = '1'
            if langs[0] == 'pt':
                langCode = '10'
            if langs[0] == 'es':
                langCode = '3'


    # Formating the season to double digit format
        if int(season) < 10: ss = "0"+season
        else: ss = season
        if int(episode) < 10: ee = "0"+episode
        else: ee = episode

    # Setting up the search string; the original tvshow name is preferable.
    # If the tvshow name lenght is less than 3 characters, append the year to the search.
        source_web=''
        resolution=''
        source_hdtv=''
        if teams.find("hdtv") > 0 :
            source_hdtv = " HDTV"
        if teams.find("420p") > 0 :
            resolution = " 420p"			
        if teams.find("720p") > 0 :
            resolution = " 720p"
        if teams.find("1080p") > 0 :
            resolution = " 1080p"
        if teams.find("webdl") > 0 :
            source_web = " WEB"				

        log.debug("resolution para procurar: " + str(resolution))	
		
		# With a space between Season and Episode, it will find double episodes uploads (using File match)
        # First try to searching using tvshow name + season + episode + resolution + source HDTV (most of them are HDTV)		
        search_string = self.CleanLTVTitle(tvshow) + " " +"S"+ss+ " " + "E"+ee #resolution + source_hdtv
        #logging.info("Legendas.TV search string: " + str(search_string))	
        search_dict = {'txtLegenda':search_string,'selTipo':'1','int_idioma':langCode}
        search_data = urllib.urlencode(search_dict)
        response = self.SearchLegendasTVSeries(search_data)  
		
        # If no subtitles are found, remove que resolution from search string and try search for WEB-DL source
        '''if response.__contains__('Nenhuma legenda foi encontrada'):
            #log( __name__ ,u" No subtitles found using the resolution + source")
            search_string = self.CleanLTVTitle(tvshow) + " " +"S"+ss + " " + "E"+ee + source_hdtv + source_web
            logging.info("Legendas.TV search string: " + str(search_string))
            search_dict = {'txtLegenda':search_string,'selTipo':'1','int_idioma':langCode}
            search_data = urllib.urlencode(search_dict)
            response = self.SearchLegendasTVSeries(search_data)'''  
			
        # If no subtitles are found, search only by Tvshow + season + episode.
        '''if response.__contains__('Nenhuma legenda foi encontrada'):
            #log( __name__ ,u" No subtitles found using the source")
            search_string = self.CleanLTVTitle(tvshow) + " " +"S"+ss+ " " + "E"+ee
            logging.info("Legendas.TV search string: " + str(search_string))
            search_dict = {'txtLegenda':search_string,'selTipo':'1','int_idioma':langCode}
            search_data = urllib.urlencode(search_dict)
            response = self.SearchLegendasTVSeries(search_data) ''' 
			
        page = self.to_unicode_or_bust(response)
        soup = BeautifulSoup(page)

        span_results = soup.find('td',{'id':'conteudodest'}).findAll('span')

        for span in span_results:
        # Jumping season packs
            if span.attrs == [('class', 'brls')]:
                continue
            td = span.find('td',{'class':'mais'})

            # Translated and original titles from LTV, the LTV season number and the
            # scene release name of the subtitle. If a movie is retrieved, the re.findall
            # will raise an exception and will continue to the next loop.
            reResult = re.findall("(.*) - [0-9]*",self.CleanLTVTitle(td.contents[2]))
            if reResult: ltv_title = reResult[0]
            else:
                ltv_title = self.CleanLTVTitle(td.contents[2])

            reResult = re.findall("(.*) - ([0-9]*)",self.CleanLTVTitle(td.contents[0].contents[0]))
            if reResult: ltv_original_title, ltv_season = reResult[0]
            else:
                ltv_original_title = self.CleanLTVTitle(td.contents[0].contents[0])
                ltv_season = 0

            release = td.parent.parent.find('span',{'class':'brls'}).contents[0]
            if not ltv_season:
                reResult = re.findall("[Ss]([0-9]+)[Ee][0-9]+",release)
                if reResult: ltv_season = re.sub("^0","",reResult[0])

            if not ltv_season: continue

            # This is the download ID for the subtitle.
            download_id = re.search('[a-z0-9]{32}',td.parent.parent.attrs[1][1]).group(0)

            # Find the language of the subtitle extracting it from a image name,
            # and convert it to the OpenSubtitles format.
            ltv_lang = re.findall("images/flag_([^.]*).gif",span.findAll('td')[4].contents[0].attrs[0][1])
            if ltv_lang: ltv_lang = ltv_lang[0]
            if ltv_lang == "br": ltv_lang = "pt-br"
            if ltv_lang == "us": ltv_lang = "en"
            if ltv_lang == "pt": ltv_lang = "pt"
            if ltv_lang == "es": ltv_lang = "es"

            # Compares the parsed and the LTV season number, then compares the retrieved titles from LTV
            # to those parsed or snatched by this service.
            # Each language is appended to a unique sequence.
            tvshow = self.CleanLTVTitle(tvshow)
            if int(ltv_season) == int(season):
                SubtitleResult = {"release" : release,"lang" : 'pt-br', "link" : download_id, "page" : self.url}
                if re.findall("^%s" % (tvshow),ltv_original_title) or self.comparetitle(ltv_title,tvshow):
                    sub1.append( SubtitleResult )
                else:
                    reResult = re.findall("[Ss][0-9]+[Ee]([0-9]+)",release)
                    if reResult: LTVEpisode = re.sub("^0","",reResult[0])
                    else: LTVEpisode = 0
                    if int(LTVEpisode) == int(episode):
                        PartialSubtitles.append( SubtitleResult )
        if not len(sub1): sub1.extend(PartialSubtitles)
        return sub1

    def chomp(self,s):
        s = re.sub("[ ]{2,20}"," ",s)
        a = re.compile("(\r|\n|^ | $|\'|\"|,|;|[(]|[)])")
        b = re.compile("(\t|-|:|\/)")
        s = b.sub(" ",s)
        s = re.sub("[ ]{2,20}"," ",s)
        s = a.sub("",s)
        return s

    def CleanLTVTitle(self,s):
        s = self.Uconvert(s)
        s = re.sub("[(]?[0-9]{4}[)]?$'","",s)
        s = self.chomp(s)
        s = s.title()
        return s

    def shiftarticle(self,s):
        for art in [ 'The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le' ]:
            x = '^' + art + ' '
            y = ', ' + art
            if re.search(x, s):
                return re.sub(x, '', s) + y
        return s

    def unshiftarticle(self,s):
        for art in [ 'The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le' ]:
            x = ', ' + art + '$'
            y = art + ' '
            if re.search(x, s):
                return y + re.sub(x, '', s)
        return s

    def noarticle(self,s):
        for art in [ 'The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le' ]:
            x = '^' + art + ' '
            if re.search(x, s):
                return re.sub(x, '', s)
        return s

    def notag(self,s):
        return re.sub('<([^>]*)>', '', s)

    def compareyear(self,a, b):
        if int(b) == 0:
            return 1
        if abs(int(a) - int(b)) <= YEAR_MAX_ERROR:
            return 1
        else:
            return 0

    def comparetitle(self,a, b):
            if (a == b) or (self.noarticle(a) == self.noarticle(b)) or (a == self.noarticle(b)) or (self.noarticle(a) == b) or (a == self.shiftarticle(b)) or (self.shiftarticle(a) == b):
                return 1
            else:
                return 0


    def to_unicode_or_bust(self,obj, encoding='iso-8859-1'):
         if isinstance(obj, basestring):
             if not isinstance(obj, unicode):
                 obj = unicode(obj, encoding)
         return obj

    def substitute_entity(self,match):
        ent = match.group(3)
        if match.group(1) == "#":
            # decoding by number
            if match.group(2) == '':
                # number is in decimal
                return unichr(int(ent))
            elif match.group(2) == 'x':
                # number is in hex
                return unichr(int('0x'+ent, 16))
        else:
            # they were using a name
            cp = n2cp.get(ent)
            if cp: return unichr(cp)
            else: return match.group()

    def decode_htmlentities(self,string):
        entity_re = re.compile(r'&(#?)(x?)(\w+);')
        return entity_re.subn(self.substitute_entity, string)[0]

# This function tries to decode the string to Unicode, then tries to decode
# all HTML entities, anf finally normalize the string and convert it to ASCII.
    def Uconvert(self,obj):
        try:
            obj = self.to_unicode_or_bust(obj)
            obj = self.decode_htmlentities(obj)
            obj = unicodedata.normalize('NFKD', obj).encode('ascii','ignore')
            return obj
        except:return obj
