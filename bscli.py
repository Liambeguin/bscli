#!/usr/bin/python
#
# inspired by https://github.com/arcresu/flexget-debian


import os, re
import logging
# this is not very pretty but meh..
logging.basicConfig(format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

import requests, json
from hashlib import md5
from docopt import docopt

from collections import namedtuple

class Episode():
	"""
	this is what the json looks like before going through __init__

   	"id": 622936,
   	"thetvdb_id": 5416091,
   	"youtube_id": null,
   	"title": "Flight 462: Part 11",
   	"season": 1,
   	"episode": 17,
   	"show": {
   		"id": 10277,
   		"thetvdb_id": 290853,
   		"title": "Fear the Walking Dead"
   	},
   	"code": "S01E17",
   	"global": 17,
   	"special": 1,
   	"description": "",
   	"date": "2016-02-28",
   	"note": {
   		"total": "12",
   		"mean": "3.2500",
   		"user": 0
   	},
   	"user": {
   		"seen": false,
   		"downloaded": false
   	},
   	"comments": "0",
   	"subtitles": []

	"""
	def __init__(self, d):
		self.__dict__ = d

	def dump(self):
		for key, value in self.__dict__.iteritems():
			print key, ' : ', value

	def viewed(self):
		print self.user['seen']

	def get_episode_id(self):
		return self.id

	def get_show_id(self):
		return self.show['id']

	def get_show_title(self):
		return self.show['title']

class BetaApi():


	def __init__(self, conffile):

		self.baseurl = "http://api.betaseries.com/"

		config = os.path.expanduser('~/.' + conffile)

		if not os.path.exists(config):
			# so lets create the file
			print "Generating configuration file..."
			user   = raw_input("login : ")
			passwd = raw_input("password : ")
			key    = raw_input("API key : ") or "4614F428BAD8"

			f = open(config, 'w')
			f.write("# This file is used by the bscli command to query betaseries' api\n")
			f.write("USER=\"" + user + "\"\n")
			f.write("PASSWORD=\"" + md5(passwd).hexdigest() + "\"\n")
			f.write("KEY=\"" +key + "\"\n")
			f.close()

		logger.debug("configuration file is %s", config)
		self.configuration = self._parse_config(config)

		self.token = self.create_token()

	def _parse_config(self, filename):
		"""Parse the configuration file"""

		options = {}
		f = open(filename)
		for line in f:
			# First, remove comments:
			if '#' in line:
				# split on comment char, keep only the part before
				line, comment = line.split('#', 1)
				# Second, find lines with an option=value:
			if '=' in line:
				# split on option char:
				option, value = line.split('=', 1)
				# strip spaces quotes and newline
				option = option.strip()
				value = value.strip(" \"\n")
				# store in dictionary:
				options[option] = value
		f.close()
		return options

	def create_token(self):
		payload={'login': self.configuration['USER'],
				'password': self.configuration['PASSWORD']
				}

		r = self._query_beta('members/auth', payload, what="post").json()

		return r['token']


	def _query_beta(self, page, payload, token=None, what=None):
		"""Send a request to the BetaSeries"""

		heads={
				'Accept': 'application/json',
				'X-BetaSeries-Version': '2.3',
				'X-BetaSeries-Key': self.configuration['KEY'],
				}
		if token:
			heads.update({"X-BetaSeries-Token": self.token})

		try:
			if what == "get" :
				ret = requests.get(self.baseurl + page, headers=heads, params=payload)
			elif what == "post" :
				ret = requests.post(self.baseurl + page, headers=heads, params=payload)
			elif what == "delete" :
				ret = requests.delete(self.baseurl + page, headers=heads, params=payload)
			else :
				print "bad usage of _query_beta() method !"
				quit()

			if ret.json()['errors']:
				for error in ret.json()['errors']:
					print error

		except (requests.exceptions.ReadTimeout,
				requests.exceptions.ConnectTimeout,
				requests.exceptions.ConnectionError) as e :
			print "something went wrong ..."

		return ret

	def get_unseen(self, single=False, filter_show=None):

		ret = []
		shows = []

		payload = {
				  'specials' : True,
				  }

		ep_list = self._query_beta('episodes/list', payload, self.token, what="get").json()

		for unseen in ep_list['shows']:
			unseen_episodes = []
			for episode in unseen['unseen']:
				unseen_episodes.append({'code':episode['code'],
					'id':episode['id'],
					'rate':float(episode['note']['mean'])/5.0*100})
				if single:
					break

			shows.append({'title':unseen['title'], 'episodes':unseen_episodes})

		if filter_show:
			for i in shows:
				if  filter_show.lower() in i['title'].lower():
					ret.append(i)
		else:
			ret = shows

		return ret


	def mark_viewed(self, episode_id, bulk=True, note=None):

		payload = { 'id' : episode_id,
				  'note' : note,
				  'bulk' : bulk,
				  }

		ret = self._query_beta('episodes/display', payload, self.token, "get")
		ep = Episode(ret.json()['episode'])

		if ep.user['seen']:
			self.unmark_viewed(episode_id)

		ret = self._query_beta('episodes/watched', payload, self.token, "post")

		return ret

	def unmark_viewed(self, episode_id):

		payload = { 'id' : episode_id }
		ret = self._query_beta('episodes/watched', payload, self.token, "delete")
		return ret

	def get_latest(self, show_id):
		payload = { 'id' : show_id }
		ret = self._query_beta('episodes/latest', payload, self.token, "get").json()
		latest_ep = Episode(ret['episode'])
		return latest_ep


	def get_next(self, show_id):
		payload = { 'id' : show_id }
		ret = self._query_beta('episodes/next', payload, self.token, "get").json()
		next_ep = Episode(ret['episode'])
		return next_ep

	def test(self, test):
	#	ret = self._query_beta('episodes/display', {'id': '622936'} , self.token, "get")
	#	ep = Episode(ret.json()['episode'])
	#	ep.dump()
		ep = self.get_next(test)
		print ep.get_show_title()
		print ep.get_show_id()
		print ep.date




def main():
	"""Interract with the BetaSeries API """

	__doc__ = """Usage:
	%(name)s [options] [-ps] [-f FILTER] watchlist
	%(name)s [options] [-n NOTE] viewed ID
	%(name)s [options] test <foo>
	%(name)s -h | --help | --version

Options:
 --version             Show version and exit
 -v, --verbose         Show debug information
 -s, --single          Only one episode
 -f, --filter FILTER   Filter output
 -n, --note NOTE       Give a note to a viewed episode
 -p, --plain           Print a machine readable output
 -h, --help            Show this help message and exit


""" % {'name': os.path.basename(__file__)}

	arguments = docopt(__doc__, version="0.1")

	conffile=os.path.basename(__file__) + ".conf"

	if arguments['--verbose']:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)

	logger.debug('Arguments are: \n%s\n', arguments)

	try:
		beta = BetaApi(conffile)

		if arguments['watchlist']:
			ep_list = beta.get_unseen(single=arguments['--single'],
					filter_show=arguments['--filter'])

			if arguments['--plain']:
				for show in ep_list:
					for episode in show['episodes']:
						print str(episode['id']) + ":" + \
								show['title'] + " " + episode['code']
			else:
				print ep_list

		if arguments['viewed']:
			if re.search('^[0-9]{6}$', arguments['ID']):
				ep_list = beta.mark_viewed(arguments['ID'], note=arguments['NOTE'])
			else:
				# use unseen list and grep episode id
				print "Not yet implemented..."

		if arguments['test']:
			ep_list = beta.test(arguments['<foo>'])


	except KeyboardInterrupt:
		print "Interrupted by user."




if __name__ == "__main__":
	main()

# vim: cc=80 :
