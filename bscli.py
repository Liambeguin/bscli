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
	def __init__(self, d):
		self.__dict__ = d

	def dump(self):
		for key, value in self.__dict__.iteritems():
			print key, ' : ', value

	def viewed(self):
		print self.user['seen']

	def get_show_id(self):
		return self.show['id']

	def get_show_title(self):
		return self.show['title']


class Event():
	def __init__(self, d):
		self.__dict__ = d

	def dump(self):
		for key, value in self.__dict__.iteritems():
			print key, ' : ', value
	def pprint(self):
		text = re.sub("\</a\>","", self.html)
		text = re.sub("\<.*\>","", text)

		print self.date + " : " + self.user + " " + text



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

###############################################################################
#### EPISODES
###############################################################################

	def get_unseen(self):

		shows = []
		payload = { 'specials' : True, }

		ep_list = self._query_beta('episodes/list', payload, self.token, what="get").json()

		for unseen in ep_list['shows']:
			unseen_episodes = []
			for episode in unseen['unseen']:
				unseen_episodes.append(Episode(episode))

			shows.append({'title':unseen['title'], 'episodes':unseen_episodes})

		# returns a list of shows containing a title and a list of Episode objects
		return shows


	def mark_viewed(self, episode_id, bulk=True, note=None):

		payload = { 'id' : episode_id,
				  'note' : note,
				  'bulk' : bulk,
				  }

		ret = self._query_beta('episodes/display', payload, self.token, "get")
		ep = Episode(ret.json()['episode'])

		if ep.viewed():
			self.unmark_viewed(episode_id)

		ret = self._query_beta('episodes/watched', payload, self.token, "post")

		return ret

	def unmark_viewed(self, episode_id):
		payload = { 'id' : episode_id }
		ret = self._query_beta('episodes/watched', payload, self.token, "delete")
		return ret

###############################################################################
#### SHOWS
###############################################################################

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

###############################################################################
#### MEMBERS
###############################################################################

	def search_members(self, username):
		payload = { 'login': username, }
		ret = self._query_beta('members/search', payload, self.token, "get").json()

		return ret['users'][0]

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
			event_list.append(Event(elt))

		return event_list



###############################################################################
#### MISC
###############################################################################

	def test(self, test):
		user = self.search_members(test)
		event_list = self.get_timeline(user['id'])

		for i in event_list:
			i.pprint()





def main():
	"""Interract with the BetaSeries API """

	__doc__ = """Usage:
	%(name)s [options] [-ps] [-f FILTER] watchlist
	%(name)s [options] [-n NOTE] viewed ID
	%(name)s [options] [--max NUMBER] timeline USERNAME
	%(name)s [options] test <foo>
	%(name)s -h | --help | --version

Options:
 --version             Show version and exit
 -v, --verbose         Show debug information
 -s, --single          Only one episode
 -f, --filter FILTER   Filter output
 --max NUMBER          Limit number of events in timeline
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
			unseen_list = beta.get_unseen()
			for show in unseen_list:
				if arguments['--filter'] \
						and arguments['--filter'] in show['title'].lower() \
						or not arguments['--filter']:

					for episode in show['episodes']:
						if arguments['--plain']:
							print str(episode.id) + ":" + \
									show['title'] + " " + episode.code
						else:
							# Could use a pretty_print here
							print show['title'] + " " + episode.code

						if arguments['--single']: break


		if arguments['viewed']:
			if re.search('^[0-9]{6}$', arguments['ID']):
				beta.mark_viewed(arguments['ID'], note=arguments['--note'])
			else:
				ep = []
				unseen_list = beta.get_unseen()
				for show in unseen_list:
					for episode in show['episodes']:
						if arguments['ID'].strip().lower() in show['title'].lower():
							ep.append(episode)

				if len(ep) > 1:
					print("Please try again with one of these codes")
					for i in ep:
						print str(i.id) + ":" + i.show['title'] + i.code
				else:
					print ep[0].id
					beta.mark_viewed(ep[0].id, note=arguments['--note'])

		# TODO if no USERNAME is given use /timeline/friends instead
		if arguments['timeline']:
			user = beta.search_members(arguments['USERNAME'])
			event_list = beta.get_timeline(user['id'], nbpp=arguments['--max'] )

			for i in event_list:
				i.pprint()

		if arguments['test']:
			ep_list = beta.test(arguments['<foo>'])


	except KeyboardInterrupt:
		print "Interrupted by user."




if __name__ == "__main__":
	main()

# vim: cc=80 :
