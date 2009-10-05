# -*- coding: utf-8 -*-

#   This file is part of periscope.
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    periscope is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with emesene; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import zipfile, os, urllib2, urllib, xml.dom.minidom, logging, traceback

import SubtitleDatabase

SS_LANGUAGES = {"en": "English",
				"se": "Swedish",
				"da": "Danish",
				"fi":"Finnish",
				"no": "Norwegian",
				"fr" : "French",
				"es" : "Spanish",
				"is" : "Icelandic"}

class SubtitleSource(SubtitleDatabase.SubtitleDB):
	url = "http://www.subtitlesource.org/"
	site_name = "SubtitleSource"

	def __init__(self):
		super(SubtitleSource, self).__init__(SS_LANGUAGES)

		#http://www.subtitlesource.org/api/xmlsearch/Heroes.S03E09.HDTV.XviD-LOL/all/0
		#http://www.subtitlesource.org/api/xmlsearch/heroes/swedish/0

		self.host = "http://www.subtitlesource.org/api/xmlsearch"
			
	def process(self, filename, langs):
		''' main method to call on the plugin, pass the filename and the wished 
		languages and it will query the subtitles source '''
		if os.path.isfile(filename):
			filename = os.path.basename(filename).rsplit(".", 1)[0]
		try:
			subs = self.query(filename, langs)
			if not subs and filename.rfind(".[") > 0:
				# Try to remove the [VTV] or [EZTV] at the end of the file
				teamless_filename = filename[0 : filename.rfind(".[")]
				subs = self.query(teamless_filename, langs)
				return subs
			else:
				return subs
		except Exception, e:
			logging.error("Error raised by plugin %s: %s" %(self.__class__.__name__, e))
			traceback.print_exc()
			return []
	
	def query(self, token, langs=None):
		''' makes a query on subtitlessource and returns info (link, lang) about found subtitles'''
		sublinks = []
		
		if not langs: # langs is empty of None
			languages = ["all"]
		else: # parse each lang to generate the equivalent lang
			languages = [SS_LANGUAGES[l] for l in langs]
							
		for lang in languages:
			searchurl = "%s/%s/%s/0" %(self.host, urllib.quote(token), lang)
			logging.debug("dl'ing %s" %searchurl)
			page = urllib2.urlopen(searchurl, timeout=5)
			xmltree = xml.dom.minidom.parse(page)
			subs = xmltree.getElementsByTagName("sub")

			for sub in subs:
				sublang = self.getLG(self.getValue(sub, "language"))
				if langs and not sublang in langs:
					continue # The language of this sub is not wanted => Skip
				dllink = "http://www.subtitlesource.org/download/zip/%s" %self.getValue(sub, "id")
				logging.debug("Link added: %s (%s)" %(dllink,sublang))
				result = {}
				result["release"] = self.getValue(sub, "releasename")
				result["link"] = dllink
				result["lang"] = sublang
				sublinks.append(result)
		return sublinks

	def getValue(self, sub, tagName):
		for node in sub.childNodes:
			if node.nodeType == node.ELEMENT_NODE and node.tagName == tagName:
				return node.childNodes[0].nodeValue