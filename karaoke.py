#!/usr/bin/env python

import os, sys, re, time, threading, datetime, subprocess, sqlite3, tweepy

SQLITE_DB='/tmp/example.db'
CDG_DIR='/Users/adam/karaoke'
PYCDG_PATH='/Users/adam/Downloads/pykaraoke-0.7.3/'

def create_db_tables():
	conn = sqlite3.connect(SQLITE_DB)
	c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS songs (id INTEGER PRIMARY KEY, filename TEXT UNIQUE);''')
	c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS playlist (id INTEGER PRIMARY KEY, song_id INTEGER, played BOOLEAN, timestamp TIMESTAMP, nick TEXT);''')
	c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS abort (id INTEGER PRIMARY KEY, abort BOOLEAN);''')
	c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS twitter (id INTEGER PRIMARY KEY, consumer_key TEXT, consumer_secret TEXT, access_key TEXT, access_secret TEXT);''')
	c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY, nick TEXT UNIQUE, twitter TEXT);''')
	c=conn.cursor().execute('''INSERT OR IGNORE INTO abort ( id, abort ) VALUES ( 1, 0 );''')
	conn.commit()
	conn.close()

def get_twitter_credentials():
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT consumer_key, consumer_secret, access_key, access_secret FROM twitter WHERE id = 1;""")
	ret = c.fetchone()
	cn.close()
	return ret

def register_user(nick, twitter):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""INSERT OR REPLACE INTO user (nick, twitter) VALUES (?, ?);""", [nick, twitter])
	cn.commit()	
	cn.close()

def get_user_info(nick):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT id, nick, twitter FROM user WHERE nick = ?""", [nick])
	ret = c.fetchone()
	cn.close()
	return ret

def insert_song(fileName):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""INSERT OR IGNORE INTO songs (filename) VALUES (?);""", [fileName])
	cn.commit()	
	cn.close()

def set_abort(abort):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""UPDATE abort SET abort = ? WHERE id = 1;""", [abort])
	cn.commit()	
	cn.close()

def check_abort():
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT abort FROM abort;""")
	ret = c.fetchone()
	cn.commit()	
	cn.close()
	return not (ret is None or ret[0] == 0)

def get_song(songID):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT filename, id FROM songs WHERE id = ?;""", [songID])
	ret = c.fetchone()
	cn.close()
	return ret

def get_queue_count():
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT count(*) FROM playlist WHERE played = 0;""")
	ret = c.fetchone()
	cn.close()
	return ret
	
def search_songs(sWords):
	searchWords = []

	for word in sWords:
		searchWords.append("%" + word + "%")

	query = "SELECT id, filename FROM songs WHERE "

	wordCount = 0
	for word in searchWords:
		if wordCount > 0:
			query += " AND "
		query += "filename LIKE ?"

		wordCount += 1

	query += ";"

	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str

	c = cn.cursor().execute(query, searchWords)

	results = []
	for row in c.fetchall():
		results.append([row[0], row[1]])

	cn.close()

	return results

def queue_song(nick, songID):
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	now = datetime.datetime.now()
	cn.cursor().execute("""INSERT INTO playlist ( timestamp, nick, song_id, played ) VALUES ( ?, ?, ?, ? )""", [ now, nick, songID, 0] )
	cn.commit()
	cn.close()

def find(phenny, input):
	sWords = re.sub("\.find\ ?", "", input).split(" ")

	if len(sWords) < 1:
		phenny.write(('PRIVMSG', input.nick), "Search query must be 3 or more characters")
		return

	retStr = "Results for search: %s" % ((" ").join(sWords))
	phenny.write(('PRIVMSG', input.nick), retStr)

	for row in search_songs(sWords):
		phenny.write(('PRIVMSG', input.nick), str(row[0]) + ": " + os.path.basename(str(row[1])))
		time.sleep(1)

	phenny.write(('PRIVMSG', input.nick), "End Results")
	
find.commands = ['find']
find.priority = 'medium'

def register(phenny, input):
	args = re.sub("\.find\ ?", "", input).split(" ")

	if len(args) < 2:
		phenny.write(('PRIVMSG', input.nick), "Register requires more than one argument")
		return

	register_user(input.nick, args[1])
	phenny.write(('PRIVMSG', input.nick), "Registered user %s to twitter account %s!" % (input.nick, args[1]))

register.commands = ['register']
register.priority = 'medium'

def rebuild_cache(phenny, input):
	if not input.admin:
		return

	files = get_cdg_files(CDG_DIR)
	phenny.say("Updating cache for %d files..." % (len(files)))

	for file in files:
		insert_song(file)

	phenny.say("Cache Updated!")

rebuild_cache.commands = ['rebuild_cache']
rebuild_cache.priority = 'medium'

def play(phenny, input):
	args = re.sub("\.play\ ?", "", input).split(" ")

	if len(args) < 1 or len(args[0]) < 1:
		phenny.say("Play command requires 1 argument...")
		return
	elif not str(args[0]).isdigit():
		phenny.say("Play command requires a numeric argument...")
		return

	song = get_song(args[0])

	if song == None or len(song) < 2:
		phenny.say("Song ID %d not found..." % (args[0]))
		return

	playFile = str(song[0])
	playId = str(song[1])
	phenny.say("Queueing file: %s" % (playFile))
	queue_song(input.nick, playId)

play.commands = ['play']
play.priority = 'medium'

def queue(phenny, input):
	res = get_queue_count()
	phenny.say("There are currently %s songs waiting to play..." % (res[0]))

queue.commands = ['queue']
queue.priority = 'medium'

def abort(phenny, input):
	if input.admin:
		set_abort(1)

abort.commands = ['abort']
abort.priority = 'medium'

def get_cdg_files(dir):
	basedir = dir
	subdirlist = []
	file_list = []
	for f in os.listdir(dir):
		if os.path.isfile(dir + "/" + f):
			if f.endswith(".cdg") or f.endswith(".mp4"):
				file_list.append(dir + "/" + f)		
		else:
			subdirlist.append(os.path.join(basedir, f))

	for subdir in subdirlist:
		for file in get_cdg_files(subdir):
			file_list.append(file)

	return file_list

def setup(phenny): 
	def monitor(phenny): 
		twitter = None
		auth_info = get_twitter_credentials()

		if auth_info != None and len(auth_info) > 3:
			auth = tweepy.OAuthHandler(auth_info[0], auth_info[1])
			auth.set_access_token(auth_info[2], auth_info[3])
			twitter = tweepy.API(auth)

		time.sleep(5)
		while True: 
			cn = sqlite3.connect(SQLITE_DB)
			c=cn.cursor().execute('''SELECT songs.filename, playlist.id, playlist.nick FROM PLAYLIST INNER JOIN songs ON song_id = songs.id WHERE playlist.played = 0 ORDER BY timestamp LIMIT 1;''')
			res = c.fetchone()
			if (res != None):
				cn.cursor().execute('''UPDATE playlist set played = 1 WHERE id = ?;''', [ res[1] ])
				cn.commit()

				for channel in phenny.config.channels:
					play_message = "%s will now be singing %s" % (res[2], os.path.basename(res[0]))

					user_info = get_user_info(res[2])
					twitter_user = res[2]

					if user_info != None:	
						twitter_user = "@" + str(user_info[2])
							
					twitter_message = ". %s will now be singing %s" % (twitter_user, os.path.basename(res[0]))

					phenny.msg(channel, play_message)

					if twitter != None:
						try: 
							twitter.update_status(twitter_message)
						except tweepy.error.TweepError, e:
							print "Twitter error({0}): {1}".format(e.response.status, e.reason)

				PLAYERS = { }

				PLAYERS['cdg'] = ["python", PYCDG_PATH + '/pycdg.py', "-w 800", "-h 600", res[0]]
				PLAYERS['mp4'] = ["mplayer", "-fs", res[0]]

				ext = res[0].lower()[len(res[0]) - 3:len(res[0])]

				p = subprocess.Popen(PLAYERS[ext])

				while p.poll() is None:
					if check_abort():
						p.terminate()
						set_abort(0)
					time.sleep(1)

				for channel in phenny.config.channels:
					phenny.msg(channel, "Done playing: %s" % (os.path.basename(res[0])))

				time.sleep(10)

			cn.close()
			time.sleep(5)

	targs = (phenny,)
	t = threading.Thread(target=monitor, args=targs)
	t.start()
	
def init():
	create_db_tables()

init()

if __name__ == '__main__':
	find(None, 'all')
