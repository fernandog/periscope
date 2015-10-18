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

#    Initial version coded by Gastao Bandeira
#    Bug fix and minor changes by Rafael Torres
#    Improved search and new LegendasTV website by Fernando G

import zipfile
import shutil
import ConfigParser
import random
import socket

import cookielib, urllib2, urllib, sys, re, os, time, unicodedata, logging
from BeautifulSoup import BeautifulSoup
from htmlentitydefs import name2codepoint as n2cp
from datetime import date

import SubtitleDatabase
import subprocess

log = logging.getLogger(__name__)
opener = ""
cj = ""
Logado = False
naodisponivel = False

class LegendasTV(SubtitleDatabase.SubtitleDB):
    url = "http://legendas.tv"
    site_name = "LegendasTV"

    def __init__(self, config, cache_folder_path):
        super(LegendasTV, self).__init__(None)
        self.tvshowRegex = re.compile('(?P<show>.*)S(?P<season>[0-9]{2})E(?P<episode>[0-9]{2}).(?P<teams>.*)', re.IGNORECASE)
        self.tvshowRegex2 = re.compile('(?P<show>.*).(?P<season>[0-9]{1,2})x(?P<episode>[0-9]{1,2}).(?P<teams>.*)', re.IGNORECASE)
        self.movieRegex = re.compile('(?P<movie>.*)[\_\.|\[|\(| ]{1}(?P<year>(?:(?:19|20)[0-9]{2}))(?P<teams>.*)', re.IGNORECASE)
        self.user = None
        self.password = None
        self.unrar = None
        self.sub_ext = None
        try:
            self.user = config.get("LegendasTV", "user")
            self.password = config.get("LegendasTV", "pass")
            self.unrar = config.get("LegendasTV", "unrarpath")
            self.sub_ext = config.get("LegendasTV", "supportedSubtitleExtensions")
            self.nma_api = config.get("LegendasTV", "nma-api")
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
        if not self.unrar or self.unrar == "" or not os.path.isfile(self.unrar):
            log.error("LegendasTV requires Unrar. Select the folder and executable of your unrar in your ~/.config/periscope/config file")
            return []
        self.LegendasTVLogin()
        if Logado == True and naodisponivel == False:
            arquivo = self.getFileName(filepath)
            dados = {}
            dados = self.guessFileData(arquivo)
            log.debug(" Dados: " + str(dados))
            if dados['type'] == 'tvshow':
                subtitles = self.LegendasTVSeries(filepath, dados['name'], str(dados['season']), str(dados['episode']), str(dados['teams']), langs)
                log.debug(" Found " + str(len(subtitles)) + " results: " + str(subtitles))
                log.debug(" Subtitles: " + str(subtitles))
            elif dados['type'] == 'movie':
                subtitles = self.LegendasTVMovies(filepath, dados['name'], dados['year'], langs)
            else:
                subtitles = self.LegendasTVMovies(filepath, dados['name'], '', langs)
            return subtitles
        else:
            log.debug("Nao logado")
            return []

    def getFileName(self, filepath):
        filename = os.path.basename(filepath)
        if filename.endswith(('.avi', '.wmv', '.mov', '.mp4', '.mpeg', '.mpg', '.mkv')):
            fname = filename.rsplit('.', 1)[0]
        else:
            fname = filename
        return fname

    def guessFileData(self, filename):
        filename = unicode(self.getFileName(self.Uconvert(filename)).lower()).replace("web-dl", "webdl").replace("web.dl", "webdl").replace("web dl", "webdl")
        log.debug(filename)
        matches_tvshow = self.tvshowRegex.match(filename)
        if matches_tvshow: # It looks like a tv show
            log.debug(" Using Regex1")
            (tvshow, season, episode, teams) = matches_tvshow.groups()
            tvshow = tvshow.replace(".", " ").strip()
            tvshow = tvshow.replace("_", " ").strip()
            teams = teams.split('.')
            if len(teams) == 1:
                teams = teams[0].split('-')
            return {'type' : 'tvshow', 'name' : tvshow.strip(), 'season' : int(season), 'episode' : int(episode), 'teams' : teams}
        else:
            matches_tvshow = self.tvshowRegex2.match(filename)
            if matches_tvshow:
                log.debug(" Using Regex2")
                (tvshow, season, episode, teams) = matches_tvshow.groups()
                tvshow = tvshow.replace(".", " ").strip()
                tvshow = tvshow.replace("_", " ").strip()
                teams = teams.split('.')
                if len(teams) == 1:
                    teams = teams[0].split('_')
                return {'type' : 'tvshow', 'name' : tvshow.strip(), 'season' : int(season), 'episode' : int(episode), 'teams' : teams}
            else:
                matches_movie = self.movieRegex.match(filename)
                if matches_movie:
                    (movie, year, teams) = matches_movie.groups()
                    movie = movie.replace(".", " ").strip()
                    movie = movie.replace("_", " ").strip()
                    teams = teams.split('.')
                    if len(teams) == 1:
                        teams = teams[0].split('_')
                    part = None
                    if "cd1" in teams:
                        teams.remove('cd1')
                        part = 1
                    if "cd2" in teams:
                        teams.remove('cd2')
                        part = 2
                    return {'type' : 'movie', 'name' : movie.strip(), 'year' : year, 'teams' : teams, 'part' : part}
                else:
                    return {'type' : 'unknown', 'name' : filename, 'teams' : []}

    def LegendasTVLogin(self):
        '''Function for login on LegendasTV using username and password from config file'''
        global opener, Logado, naodisponivel
        if Logado == False and naodisponivel == False:
            leg_url = self.url
            cj = cookielib.CookieJar()
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
            opener.addheaders = [('User-agent', ('Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36'))]
            urllib2.install_opener(opener)
            login_data = urllib.urlencode({'data[User][username]':self.user, 'data[User][password]':self.password})

            try:
                response = opener.open(self.url+'/login', login_data, timeout=30).read()
                log.debug(" Tentando logar no LegendasTV")
            except socket.timeout:
                log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
            except IOError, e:
                if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                    log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                    naodisponivel = True
                elif e.message == 'timed out':
                    log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                else:
                    log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
                Logado = False
            except:
                log.info(" Nao foi possivel pesquisar no LegendasTV.")
                Logado = False
            else:
                if response.__contains__('alert alert-error'):
                    log.error(" Senha ou usuario invalido")
                    Logado = False
                elif response.__contains__('An Internal Error Has Occurred'):
                    log.error(" Internal error")
                    Logado = False
                elif response.__contains__(">"+str(self.user)+"</a><span>"):
                    log.info(" Logado com sucesso no LegendasTV!")
                    Logado = True
                    for cookie in cj:
                        cookie.expires = time.time() + 14 * 24 * 3600
                else:
                    log.error(" Nao foi possivel logar no LegendasTV")
                    Logado = False


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

    def extractFile(self, fname, extract_path, extractedFiles=[]):
        ''' Uncompress the subtitle '''
        if fname in extractedFiles:
            return
        if zipfile.is_zipfile(fname):
            log.debug(" Unzipping file " + fname)
            zf = zipfile.ZipFile(fname, "r")
            zf.extractall(extract_path)
            zf.close()
        elif fname.endswith('.rar'):
            try:
                '''Try to use unrar from folder in config file'''
                log.debug(" Extracting file " + fname)
                subprocess.call([self.unrar, 'e', '-y', '-inul', fname, extract_path])
            except OSError as e:
                log.error("OSError [%d]: %s at %s" % (e.errno, e.strerror, e.filename))
            except:
                log.error("General error:" + str(sys.exc_info()[0]))
        else:
            log.error("Unknown file format: " + fname)

        extractedFiles.append(fname)

        fs_encoding = sys.getfilesystemencoding()
        for root, dirs, files in os.walk(extract_path.encode(fs_encoding), topdown=False):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".zip", ".rar"]:
                    self.extractFile(os.path.join(root, f), extract_path, extractedFiles)

    def downloadFile(self, url, srtfilename):
        ''' Downloads the given url to the given filename '''
        subtitle = ""
        #Added the random number so two tvshow subtitles from the same season/episode but with releases/quality different can be downloaded
        extract_path = os.path.join(srtfilename.replace(self.getFileName(srtfilename), ''), str(url) + "-" + str(random.randint(1, 99999)))
        log.debug(" Path: " + str(extract_path))
        requests_log = logging.getLogger("requests")
        requests_log.setLevel(logging.WARNING)
        ltv_sub = ""
        try:
            #self.LegendasTVLogin()
            download_url = self.url + "/downloadarquivo/" + str(url)
            log.debug(download_url)
            response = opener.open(download_url, timeout=30)
            ltv_sub = response.read()
            headers = response.info()
            length = headers.getheaders("Content-Length")[0]
            log.debug("File length:" + str(length))
            #log.debug(ltv_sub)
            #log.info(headers)
            if int(length) < 100:
                global Logado
                Logado = False
                self.LegendasTVLogin()
                response = opener.open(download_url, timeout=30)
                ltv_sub = response.read()
                headers = response.info()
                length = headers.getheaders("Content-Length")[0]
                log.debug(" Novo tamanho de arquivo:" + str(length))
        except socket.timeout:
            log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
            return False
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                naodisponivel = True
            elif e.message == 'timed out':
                log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
            else:
                log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
            return False
        except:
            log.info(" Nao foi possivel pesquisar no LegendasTV.")
            return False
        else:
            if "attachment" in str(headers) and int(length) > 100:
                os.makedirs(extract_path)
                fname = os.path.join(extract_path, str(url))
                fname += '.rar'
                f = open(fname, 'wb')
                f.write(ltv_sub)
                f.close()

                self.extractFile(fname, extract_path)

                legendas_tmp = []
                fs_encoding = sys.getfilesystemencoding()
                for root, dirs, files in os.walk(extract_path.encode(fs_encoding), topdown=False):
                    for file in files:
                        dirfile = os.path.join(root, file)
                        log.debug("Diretorio: " + str(dirfile))
                        ext = os.path.splitext(dirfile)[1][1:].lower()
                        log.debug(" file [%s] extension[%s]" % (file, ext))
                        if ext in self.sub_ext:
                            log.debug(" adicionando " + os.path.basename(dirfile))
                            legendas_tmp.append(dirfile)
                if len(legendas_tmp) == 0:
                    log.info(' Nenhuma legenda descompactada')
                    return False
                else:
                    log.debug(' Legenda baixada e descompactada')
            else:
                log.info(' Nao e um arquivo RAR de legenda. Tamanho: ' + str(length))
                return False

            '''Verify the best subtitle in case of a pack for multiples releases'''
            legenda_retorno = self.CompareSubtitle(srtfilename, legendas_tmp)
            if legenda_retorno == '':
                log.info(" Nenhuma legenda compativel")
                shutil.rmtree(extract_path)
                srtfilename = ''
                return False
            else:
                log.debug(" Renaming [%s] to [%s] " % (os.path.join(extract_path, legenda_retorno), srtfilename))
                shutil.move(os.path.join(extract_path, legenda_retorno), srtfilename)
                shutil.rmtree(extract_path)

    def NMA(self, releasename, subtitle):

        try:
            data = urllib.urlencode({"apikey":self.nma_api, "application":"Legendas.TV", "event":str(subtitle), "description":"Arquivo: " + str(releasename)})
            response = urllib2.urlopen("https://www.notifymyandroid.com/publicapi/notify", data, timeout=30)
        except Exception, e:
            print "Exception while running NotifyMyAndroid: " + repr(e)

    def CompareSubtitle(self, releaseFile, subtitleList):
        '''Verify the best subtitle in case of a pack for multiples releases'''
        releaseFile = os.path.basename(releaseFile)
        release = releaseFile.lower().replace("web-dl", "webdl").replace("web.dl", "webdl").replace("web dl", "webdl").replace("web_dl", "webdl")
        releasename = self.getFileName(release)
        nameSplit = releasename.rsplit(".", 1)[0].replace('.', ' ').replace('_', ' ').replace('-', ' ').replace("'", "").split()
        releasevideo = nameSplit[-1]
        resolutionvideo = "420p"
        if any("hdtv" in s.lower() for s in nameSplit):
            qualityvideo = "hdtv"
        if any("webrip" in s.lower() for s in nameSplit):
            qualityvideo = "webrip"
        if any("webdl" in s.lower() for s in nameSplit):
            qualityvideo = "webdl"
        if any("720p" in s.lower() for s in nameSplit):
            resolutionvideo = "720p"
        if any("1080p" in s.lower() for s in nameSplit):
            resolutionvideo = "1080p"

        log.info(" Procurando legenda: " + str(releaseFile.rsplit(".", 1)[0]) + " (Qualidade: "+ str(resolutionvideo) + "." + str(qualityvideo) + " e Equipe: " + str(releasevideo) + ")")
        bestMatch = ''
        FirstMatch = ''
        SecondMatch = ''
        FileMatch = ''
        MatchMode = ''
        for subtitle in subtitleList:
            subtitlefile = os.path.basename(subtitle)
            sub_clean = subtitlefile.lower().replace("web-dl", "webdl").replace("web.dl", "webdl").replace("web dl", "webdl").replace("web_dl", "webdl")
            subtitlename = self.getFileName(sub_clean)
            nameSplitTemp = subtitlename.rsplit(".", 1)[0].replace(" BR-PORT", "").replace('.', ' ').replace('_', ' ').replace('-', ' ').replace("'", "").split()
            log.debug(nameSplitTemp)
            releasesrt = nameSplitTemp[-1]
            resolutionsrt = "420p"
            if any("hdtv" in s.lower() for s in nameSplitTemp):
                qualitysrt = "hdtv"
            if any("webrip" in s.lower() for s in nameSplitTemp):
                qualitysrt = "webrip"
            if any("webdl" in s.lower() for s in nameSplitTemp):
                qualitysrt = "webdl"
            if any("web-dl" in s.lower() for s in nameSplitTemp):
                qualitysrt = "webdl"
            if any("web.dl" in s.lower() for s in nameSplitTemp):
                qualitysrt = "webdl"
            if any("720p" in s.lower() for s in nameSplitTemp):
                resolutionsrt = "720p"
            if any("1080p" in s.lower() for s in nameSplitTemp):
                resolutionsrt = "1080p"

            if releasename.rsplit(".", 1)[0].lower() == subtitlename.rsplit(".", 1)[0].lower().replace("web.dl", "web-dl").replace("web dl", "web-dl"):
                log.debug(" Arquivo exato: " + str(subtitlename.rsplit(".", 1)[0]))
                FileMatch = str(self.getFileName(subtitle))
            else:
                # If matched using filename, dont match by Team and quality
                if len(FileMatch) < 1:
                    #log.info(" Video: " + str(resolutionvideo.lower()) + "." + str(qualityvideo.lower()) + " / " + " Subtitle: " + str(resolutionsrt.lower()) + "." + str(qualitysrt.lower()))
                    if releasevideo.lower() == releasesrt.lower():
                        if resolutionvideo.lower() == resolutionsrt.lower() and qualityvideo.lower() == qualitysrt.lower():
                            #FirstMatch = Team and quality must be equal
                            log.info(" Qualidade: Sim e Equipe: Sim - " + str(subtitlefile))
                            FirstMatch = str(self.getFileName(subtitle))
                        elif qualityvideo.lower() == qualitysrt.lower():
                            #SecondMatch = only team must be equal (some WEB-DL are postest only with quality 720p )
                            log.info(" Qualidade: Nao e Equipe: Sim - " + str(subtitlefile))
                            SecondMatch = str(self.getFileName(subtitle))
                    else:
                        log.debug("Team not matched: " + str(subtitlename))
                        if resolutionvideo.lower() == resolutionsrt.lower() and qualityvideo.lower() == qualitysrt.lower():
                            #FirstMatch = Team and resolution must be equal
                            if resolutionvideo.lower() == '1080p' and qualityvideo.lower() == qualitysrt.lower():
                                #FirstMatch = Team different and resolution equal (1080p cases)
                                #FirstMatch = subtitlename
                                #There is the new 1080p.HDTV. Can promote anymore
                                log.info(" Qualidade: Sim e Equipe: Nao (Renomear!) - " + str(subtitlefile))
                                self.NMA(releaseFile.rsplit(".", 1)[0], subtitlefile.rsplit(".", 1)[0])
                            else:
                                log.info(" Qualidade: Sim e Equipe: Nao - " + str(subtitlefile))
                        else:
                            # Team and Resolution different
                            if 'major.crimes' in subtitlename.lower() or 'major crimes' in subtitlename.lower():
                                FirstMatch = subtitlename
                                log.info(" Qualidade: Nao e Equipe: Nao - Forcing download - " + str(subtitlefile))
                            else:
                                log.info(" Qualidade: Nao e Equipe: Nao - " + str(subtitlefile))
        #if len(FileMatch)+len(FirstMatch)+len(SecondMatch) > 1:
            log.debug("FileMatch: " + str(FileMatch) + " FirstMatch: " + str(FirstMatch) + " SecondMatch: " + str(SecondMatch))
        if len(FileMatch) > 1:
            bestMatch = FileMatch
            MatchMode = "File"
        else:
            if len(FirstMatch) > 1:
                bestMatch = FirstMatch
                MatchMode = "Equipe + Qualidade"
            else:
                bestMatch = SecondMatch
                MatchMode = "Equipe (Qualidade promovida)"
        if len(bestMatch) > 1:
            log.info(" ***** Arquivo exato: " + str(bestMatch) + " *****")
        return bestMatch

    def LegendasTVMovies(self, file_original_path, title, year, langs):

        # Initiating variables and languages.
        subtitles, sub1 = [], []

        log.debug(' movie')

        if len(langs) > 1:
            langCode = '99'
        else:
            if langs[0] == 'pt-br':
                langCode = 'portugues-br'
            if langs[0] == 'pt':
                langCode = 'portugues-pt'
            if langs[0] == 'es':
                langCode = 'espanhol'

        search = title.lower() + ' ' + year
        search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
        log.debug(" Search URL: " + str(search_url))
        log.debug(search)
        try:
            response = opener.open(search_url, timeout=30).read()
            result = response.lower()
            soup = BeautifulSoup(result)
            qtdlegendas = result.count('span class="number number_')

            if qtdlegendas > 0:
                result = []
                log.debug(" Resultado da busca: " + str(qtdlegendas) + " legenda(s)")
                # Legenda com destaque
                for html in soup.findAll("div", {"class":"destaque"}):
                    a = html.find("a")
                    link = self.url + a.get("href")
                    name = a.text
                    user = html.find("p", "data").find("a").text
                    lang = html.find("img")["title"]
                    entry = {"Link": link, "Name": name, "Lang": self.Uconvert(lang)}
                    log.debug(entry)
                    if  langCode == self.Uconvert(lang):
                        result.append(entry)

                # Legenda sem destaque
                for html in soup.findAll("div", {"class":""}):
                    a = html.find("a")
                    link = self.url + a.get("href")
                    name = a.text
                    user = html.find("p", "data").find("a").text
                    lang = html.find("img")["title"]
                    entry = {"Link": link, "Name": name, "Lang": self.Uconvert(lang)}
                    log.debug(entry)
                    if  langCode == self.Uconvert(lang):
                        result.append(entry)

                qtd = len(result)
                if qtd > 0:
                    for legendas in result:
                        log.debug(legendas["Name"])
                        log.debug(title.lower() + ' ' + year)
                        if legendas["Name"].find(title.lower() + ' ' + year) >= 0 or legendas["Name"].find(title.lower()) >= 0 or legendas["Name"].find(title.lower().replace(' ', '.') + ' ' + year) >= 0 or legendas["Name"].find(title.lower().replace(' ', '.')) >= 0:
                            link = legendas["Link"]
                            regex = re.compile(self.url + '/download/(?P<id>[0-9a-zA-Z].*)/(?P<movie>.*)/(?P<movie2>.*)')
                            try:
                                id_match = regex.match(link)
                                if id_match:
                                    id = id_match.group(1)
                                    SubtitleResult = {"release" : legendas["Name"], "lang" : 'pt-br', "link" : id, "page" : self.url}
                                    sub1.append(SubtitleResult)
                                    log.info(" Legenda " + str(legendas["Name"]) + " adicionada a fila do Periscope")
                                else:
                                    log.error(" Nao foi possivel achar o ID da legenda")
                            except:
                                log.error(" Erro ao tentar achar o ID da legenda")
                        else:
                            log.error(" Nao foi possivel achar a legenda nos resultados")
                else:
                    log.debug(" Nao houve resultados para a busca desse episodio")
            else:
                log.debug(" Nao houve resultados para a busca desse episodio")
        except socket.timeout:
            log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                naodisponivel = True
            elif e.message == 'timed out':
                log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
            else:
                log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
        return sub1

    def LegendasTVSeries(self, file_original_path, tvshow, season, episode, teams, langs):

    # Initiating variables and languages.
        subtitles, sub1, sub2, sub3, PartialSubtitles = [], [], [], [], []

        if len(langs) > 1:
            langCode = '99'
        else:
            if langs[0] == 'pt-br':
                langCode = 'portugues-br'
            if langs[0] == 'pt':
                langCode = 'portugues-pt'
            if langs[0] == 'es':
                langCode = 'espanhol'


    # Formating the season to double digit format
        if int(season) < 10: ss = "0" + season
        else: ss = season
        if int(episode) < 10: ee = "0" + episode
        else: ee = episode

        episode_a = int(episode)-1
        if episode_a < 10: eea = "0" + str(episode_a)
        else: eea = str(episode_a)

    # Setting up the search string; the original tvshow name is preferable.
    # If the tvshow name lenght is less than 3 characters, append the year to the search.
        source_web = ''
        resolution = ''
        source_hdtv = ''
        if teams.find("hdtv") > 0:
            source_hdtv = " HDTV"
        if teams.find("420p") > 0:
            resolution = " 420p"
        if teams.find("720p") > 0:
            resolution = " 720p"
        if teams.find("1080p") > 0:
            resolution = " 1080p"
        if teams.find("webdl") > 0:
            source_web = " WEB"


        search = tvshow + ' ' + 'S' + ss +'E' + ee
        search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
        log.debug(" Search URL (0): " + str(search_url))
        try:
            response = opener.open(search_url, timeout=30).read()
            result = response.lower()

            soup = BeautifulSoup(result)
            qtdlegendas = result.count('span class="number number_')
            log.debug(qtdlegendas)

            #f = open(result_page.html', 'w')
            #f.write(result)
            #f.close()

            if qtdlegendas <= 0:
                search = self.RemoveYear(tvshow) + ' ' + 'S' + ss +'E' + ee
                search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
                log.debug(" Search URL (1): " + str(search_url))
                try:
                    response = opener.open(search_url, timeout=30).read()
                    result = response.lower()
                    soup = BeautifulSoup(result)
                    qtdlegendas = result.count('span class="number number_')
                except socket.timeout:
                    log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    return sub1
                except IOError, e:
                    if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                        log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                        naodisponivel = True
                    elif e.message == 'timed out':
                        log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    else:
                        log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
                    return sub1
                except:
                    log.info(" Nao foi possivel pesquisar no LegendasTV.")
                    return sub1

            if qtdlegendas <= 0:
                search = self.RemoveYear(tvshow) + ' ' + 'S' + ss +' E' + ee
                search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
                log.debug(" Search URL (1): " + str(search_url))
                try:
                    response = opener.open(search_url, timeout=30).read()
                    result = response.lower()
                    soup = BeautifulSoup(result)
                    qtdlegendas = result.count('span class="number number_')
                except socket.timeout:
                    log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    return sub1
                except IOError, e:
                    if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                        log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                        naodisponivel = True
                    elif e.message == 'timed out':
                        log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    else:
                        log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
                    return sub1
                except:
                    log.info(" Nao foi possivel pesquisar no LegendasTV.")
                    return sub1

            if qtdlegendas <= 0:
                search = self.RemoveYear(tvshow) + ' ' + 'S' + ss +'E' + eea +'E' + ee
                search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
                log.debug(" Search URL (2): " + str(search_url))
                try:
                    response = opener.open(search_url, timeout=30).read()
                    result = response.lower()
                    soup = BeautifulSoup(result)
                    qtdlegendas = result.count('span class="number number_')
                except socket.timeout:
                    log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    return sub1
                except IOError, e:
                    if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                        log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                        naodisponivel = True
                    elif e.message == 'timed out':
                        log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    else:
                        log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
                    return sub1
                except e:
                    log.info(" Nao foi possivel pesquisar no LegendasTV - " + str(e.reason))
                    return sub1

            if qtdlegendas <= 0:
                search = tvshow.replace(".", " ").replace("_", " ") + ' ' + season +'x' + ee
                search_url = self.url +'/util/carrega_legendas_busca/' +search.replace(' ', '%20')+ '/1'
                log.debug(" Search URL (3): " + str(search_url))
                try:
                    response = opener.open(search_url, timeout=30).read()
                    result = response.lower()
                    soup = BeautifulSoup(result)
                    qtdlegendas = result.count('span class="number number_')
                except socket.timeout:
                    log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    return sub1
                except IOError, e:
                    if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                        log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                        naodisponivel = True
                    elif e.message == 'timed out':
                        log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
                    else:
                        log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
                    return sub1
                except:
                    log.info(" Nao foi possivel pesquisar no LegendasTV.")
                    return sub1

            if qtdlegendas > 0:

                result = []
                log.debug(" Resultado da busca: " + str(qtdlegendas) + " legenda(s)")
                # Legenda sem destaque
                for html in soup.findAll("div", {"class":""}):
                    a = html.find("a")
                    link = a.get("href")
                    name = a.text
                    #user = html.find("p", "data").find("a").text
                    data = int(html.find("p", "data").text[-18:][:10][-4:])
                    lang = html.find("img")["title"]
                    entry = {"Link": link, "Name": name, "Lang": self.Uconvert(lang)}
                    log.debug(entry)
                    if  langCode == self.Uconvert(lang) and data >= int(date.today().year)-1:
                        log.debug(" Legenda sem destaque encontrada")
                        result.append(entry)

                # PACK
                for html in soup.findAll("div", {"class":"pack"}):
                    a = html.find("a")
                    link = a.get("href")
                    name = a.text
                    #user = html.find("p", "data").find("a").text
                    lang = html.find("img")["title"]
                    data = int(html.find("p", "data").text[-18:][:10][-4:])
                    entry = {"Link": link, "Name": name, "Lang": self.Uconvert(lang)}
                    log.debug(entry)
                    if  langCode == self.Uconvert(lang) and data >= int(date.today().year)-1:
                        log.debug(" Legenda Pack encontrada")
                        result.append(entry)

                # Legenda com destaque
                for html in soup.findAll("div", {"class":"destaque"}):
                    a = html.find("a")
                    link = a.get("href")
                    name = a.text
                    #user = html.find("p", "data").find("a").text
                    lang = html.find("img")["title"]
                    data = int(html.find("p", "data").text[-18:][:10][-4:])
                    entry = {"Link": link, "Name": name, "Lang": self.Uconvert(lang)}
                    log.debug(entry)
                    if  langCode == self.Uconvert(lang) and data >= int(date.today().year)-1:
                        log.debug(" Legenda com destaque encontrada")
                        result.append(entry)

                qtd = len(result)
                if len(result) > 0:
                    for legendas in result:
                        if legendas["Name"].find('s'+ss + 'e'+ee) >= 0 or legendas["Name"].find(season+'x'+ee) >= 0 or legendas["Name"].find('s'+ss + ' e'+ee):
                            link = legendas["Link"]
                            regex = re.compile('/download/(?P<id>[0-9a-zA-Z].*)/(?P<tvshow>.*)/(?P<release>.*)')
                            try:
                                id_match = regex.match(link)
                                if id_match:
                                    id = id_match.group(1)
                                    SubtitleResult = {"release" : legendas["Name"], "lang" : 'pt-br', "link" : id, "page" : self.url}
                                    sub1.append(SubtitleResult)
                                    log.info(" Legenda " + str(legendas["Name"]) + " adicionada a fila do Periscope")
                                else:
                                    log.error(" Nao foi possivel achar o ID da legenda")
                            except:
                                log.error(" Erro ao tentar achar o ID da legenda")
                        elif legendas["Name"].find('s'+ss + 'e' + eea + 'e'+ee) >= 0:
                            link = legendas["Link"]
                            regex = re.compile('/download/(?P<id>[0-9a-zA-Z].*)/(?P<tvshow>.*)/(?P<release>.*)')
                            try:
                                id_match = regex.match(link)
                                if id_match:
                                    id = id_match.group(1)
                                    SubtitleResult = {"release" : legendas["Name"], "lang" : 'pt-br', "link" : id, "page" : self.url}
                                    sub1.append(SubtitleResult)
                                    log.info(" Legenda " + str(legendas["Name"]) + " adicionada a fila do Periscope")
                                else:
                                    log.error(" Nao foi possivel achar o ID da legenda")
                            except:
                                log.error(" Erro ao tentar achar o ID da legenda")
                        else:
                            log.error(" Nao foi possivel achar a legenda nos resultados")
                else:
                    log.debug(" Nao houve resultados para a busca desse episodio")
            else:
                log.debug(" Nao houve resultados para a busca desse episodio")
        except socket.timeout:
            log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
        except IOError, e:
            if hasattr(e, 'code') and hasattr(e, 'reason') and e.code in (500, 501, 502, 503, 504, 404):
                log.info(" LegendasTV nao disponivel. Nao foi possivel logar")
                naodisponivel = True
            elif e.message == 'timed out':
                log.info(" Nao foi possivel pesquisar no LegendasTV - Timeout")
            else:
                log.info(" Nao foi possivel logar no LegendasTV. Mensagem: " + str(e.reason))
        except:
            log.info(" Nao foi possivel pesquisar no LegendasTV.")
        #except:
         #   log.info(" Nao foi possivel pesquisar no LegendasTV. Exception")
        return sub1

    def chomp(self, s):
        s = re.sub("[ ]{2,20}", " ", s)
        a = re.compile("(\r|\n|^ | $|\'|\"|,|;|[(]|[)])")
        b = re.compile("(\t|-|:|\/)")
        s = b.sub(" ", s)
        s = re.sub("[ ]{2,20}", " ", s)
        s = a.sub("", s)
        return s

    def CleanLTVTitle(self, s):
        s = self.Uconvert(s)
        s = re.sub("[(]?[0-9]{4}[)]?$'", "", s)
        s = self.chomp(s)
        s = s.title()
        return s

    def RemoveYear(self, s):
        for art in ['2014', '2013', '2012', '2011', '2010', '2009', '2008', '2007', '2006', '2005', '2004', '2003', '2002', '2001', '1999']:
            if re.search(art, s):
                return re.sub(art, '', s)
        return s

    def shiftarticle(self, s):
        for art in ['The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le']:
            x = '^' + art + ' '
            y = ', ' + art
            if re.search(x, s):
                return re.sub(x, '', s) + y
        return s

    def unshiftarticle(self, s):
        for art in ['The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le']:
            x = ', ' + art + '$'
            y = art + ' '
            if re.search(x, s):
                return y + re.sub(x, '', s)
        return s

    def noarticle(self, s):
        for art in ['The', 'O', 'A', 'Os', 'As', 'El', 'La', 'Los', 'Las', 'Les', 'Le']:
            x = '^' + art + ' '
            if re.search(x, s):
                return re.sub(x, '', s)
        return s

    def notag(self, s):
        return re.sub('<([^>]*)>', '', s)

    def compareyear(self, a, b):
        if int(b) == 0:
            return 1
        if abs(int(a) - int(b)) <= YEAR_MAX_ERROR:
            return 1
        else:
            return 0

    def comparetitle(self, a, b):
        if (a == b) or (self.noarticle(a) == self.noarticle(b)) or (a == self.noarticle(b)) or (self.noarticle(a) == b) or (a == self.shiftarticle(b)) or (self.shiftarticle(a) == b):
            return 1
        else:
            return 0


    def to_unicode_or_bust(self, obj, encoding='iso-8859-1'):
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj

    def substitute_entity(self, match):
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

    def decode_htmlentities(self, string):
        entity_re = re.compile(r'&(#?)(x?)(\w+);')
        return entity_re.subn(self.substitute_entity, string)[0]

# This function tries to decode the string to Unicode, then tries to decode
# all HTML entities, anf finally normalize the string and convert it to ASCII.
    def Uconvert(self, obj):
        try:
            obj = self.to_unicode_or_bust(obj)
            obj = self.decode_htmlentities(obj)
            obj = unicodedata.normalize('NFKD', obj).encode('ascii', 'ignore')
            return obj
        except:
            return obj
