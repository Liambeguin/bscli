#!/usr/bin/python
#
# inspired by https://github.com/arcresu/flexget-debian


import os
import logging
# this is not very pretty but meh..
logging.basicConfig(format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

import requests, json
from hashlib import md5
from docopt import docopt


class BetaApi:

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
				'X-BetaSeries-Version': '2.1',
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
				print "Not yet implemented, sorry ..."
				quit()
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

		ep_list = self._query_beta('episodes/list', {},  self.token).json()

		for unseen in ep_list['shows']:
			unseen_episodes = []
			for episode in unseen['unseen']:
				unseen_episodes.append(episode['code'])
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




def main():
	"""Interract with the BetaSeries API """

	__doc__ = """Usage:
	%(name)s [options] unseen
	%(name)s -h | --help | --version

Options:
 --version             Show version and exit
 -v, --verbose         Show debug information
 -s, --single          Only one episode
 -f, --filter FILTER   Filter output
 -p, --plain           Print a machine readable output
 -h, --help            Show this help message and exit


""" % {'name': os.path.basename(__file__)}

	arguments = docopt(__doc__, version="0.1")

	conffile=os.path.basename(__file__) + ".conf"

	if arguments['--verbose']:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)

	logger.debug('Arguments are: %s', arguments)

	try:
		beta = BetaApi(conffile)

		if arguments['unseen']:
			ep_list = beta.get_unseen(single=arguments['--single'], filter_show=arguments['--filter'])

		if arguments['--plain']:
			for show in ep_list:
				for episode in show['episodes']:
					print show['title'] + " " + episode


	except KeyboardInterrupt:
		print "Interrupted by user."




if __name__ == "__main__":
	main()

# vim: cc=80 :
