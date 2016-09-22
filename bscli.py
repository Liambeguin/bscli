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
import textwrap
import string
from datetime import datetime



class Episode():
	def __init__(self, name, code, title, note, desc, ep_id, date):
		# name is show name + code
		self.name = name
		self.code = code
		# title is the episode's name
		self.title = title
		self.note = note
		self.description = desc
		self.beta_id = str(ep_id)
		self.seen = False
                # get date as an object
                self.date = datetime.strptime(date, "%Y-%m-%d")
                # display it in a nice way
                self.date = self.date.strftime("%A %b %d %Y")

	def pprint(self):
		print self.name + " (" + self.title + ")"
		print "    note: " + self.note
		print "    description: " + self.description
		print "    id: " + self.beta_id

	def get_description(self, width=80):
		print textwrap.fill(self.description)


class Show():
	def __init__(self, title, ep_list):
		self.name = title
		self.sname = self.strip_name(title)
		self.episodes = ep_list
		self.count = str(len(ep_list))
		self.next = self.strip_name(self.episodes[0].name)

	def pprint(self):
		print self.name
		for i in self.episodes:
			print "    " + i.name + " (" + i.title + ")"

	def strip_name(self, name):
		stripped  = ''.join(filter(lambda x:x in string.printable, name))
		stripped = stripped.replace("'", "")
		return stripped


class Event():
	def __init__(self, user, description, date, type):
		self.user = user
		self.description = "[ " + date + " ]:  " + user + " " + re.sub(r'(<.*">)(.*)(</a>)', r'\2', description)
		self.date = date
		self.type = type




class BetaApi():

	def __init__(self, conffile="bscli.conf"):

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
			if '#' in line:
				line, comment = line.split('#', 1)
			if '=' in line:
				option, value = line.split('=', 1)
				option = option.strip()
				value = value.strip(" \"\n")
				options[option] = value
		f.close()
		return options


	def create_token(self):
		payload={'login': self.configuration['USER'],
				'password': self.configuration['PASSWORD']
				}

		r = self._query_beta('members/auth', payload, what="post").json()

		logger.debug("TOKEN is : " +  r['token'])
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
				raise Exception("bad usage of _query_beta() method !")

			# if ret.json()['errors']:
			# 	for error in ret.json()['errors']:
			# 		print error

		except (requests.exceptions.ReadTimeout,
				requests.exceptions.ConnectTimeout,
				requests.exceptions.ConnectionError) as e :
			raise Exception("something went wrong while connecting to the server...")

		return ret

	#
	# EPISODES
	#
	def get_watchlist(self):

		shows = []
		payload = { 'specials' : False, }

		ret = self._query_beta('episodes/list', payload, self.token, what="get").json()

		shows = []
		for show in ret['shows']:
			ep_list = []
			for unseen_episode in show['unseen']:
				ep_list.append(Episode(
					show['title'] + " " + unseen_episode['code'],
					unseen_episode['code'],
					unseen_episode['title'],
					unseen_episode['note']['mean'],
					unseen_episode['description'],
					unseen_episode['id'],
                                        unseen_episode['date']))

			shows.append(Show(show['title'], ep_list))

		return shows


	def mark_episode_as(self, seen, episode_id, bulk=True, note=None):

		if not re.search('^[0-9]{6}$', episode_id):
			raise("Bad episode ID!")

		payload = { 'id' : episode_id, 'note' : note, 'bulk' : bulk }
		ret = self._query_beta('episodes/display', payload, self.token, "get")
		ep = ret.json()['episode']

		if seen and not ep['user']['seen']:
			logger.debug('marking %s as seen' %(episode_id))
			self._query_beta('episodes/watched', payload, self.token, "post")
		elif not seen and ep['user']['seen']:
			logger.debug('marking %s as unseen' %(episode_id))
			payload = { 'id' : episode_id }
			self._query_beta('episodes/watched', payload, self.token, "delete")
		else:
			logger.debug('%s already marked as asked' %(episode_id))





	#
	# SHOWS
	#
	def search_show(self, search):
		payload = {
				'title' : search,
				'summary' : True,
				}

		ret = self._query_beta('shows/search', payload, self.token, "get").json()

		return ret['shows']

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




	#
	# MEMBERS
	#
	def search_members(self, username):
		payload = { 'login': username, }
		ret = self._query_beta('members/search', payload, self.token, "get").json()

		return ret['users'][0]

	# TODO: add something to get the whole timeline
	def get_timeline(self, userid, nbpp=100, since=None, types=None):
		payload = {
				'id': userid,
				'nbpp': nbpp,
				'since_id': since,
				'types': types,
				}
		ret = self._query_beta('timeline/member', payload, self.token, "get").json()

		event_list = []
		for elt in ret['events']:
			event_list.append(Event(
					type=elt['type'],
					description=elt['html'],
					user=elt['user'],
					date=elt['date']))

		return event_list







def main():
	"""Interract with the BetaSeries API """

	__doc__ = """Usage:
	%(name)s [options] [-a] [watchlist|w]
	%(name)s [options] [--max NUMBER] timeline USERNAME
	%(name)s -h | --help | --version

Options:
 --version             Show version and exit
 -v, --verbose         Show debug information
 -a, --all             Show all episodes
 --max NUMBER          Limit number of events in timeline
 -h, --help            Show this help message and exit


""" % {'name': os.path.basename(__file__)}

	arguments = docopt(__doc__, version="0.2")

	conffile=os.path.basename(__file__) + ".conf"

	if arguments['--verbose']:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)

	logger.debug('Arguments are: \n%s\n', arguments)

	beta = BetaApi(conffile)

	if arguments['watchlist'] or arguments['w']:
		watchlist = beta.get_watchlist()
		for show in watchlist:
			if arguments['--all']:
				for episode in show.episodes:
					print episode.name + "    [ " + episode.beta_id + " ]"
			else:
				print show.next

	# TODO if no USERNAME is given use /timeline/friends instead
	if arguments['timeline']:
		user = beta.search_members(arguments['USERNAME'])
		event_list = beta.get_timeline(user['id'], nbpp=arguments['--max'] )

		for i in event_list:
			print(i.description)




if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print "Interrupted by user."



# vim: cc=80 :
