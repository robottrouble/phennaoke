#!/usr/bin/env python

import os, re, time, threading, datetime, subprocess
import sqlite3

SQLITE_DB='/tmp/example.db'
CDG_DIR='/Volumes/Karaoke/'
PYCDG_PATH='/Users/adam/Downloads/pykaraoke-0.7.3/'

conn = sqlite3.connect(SQLITE_DB)
c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS songs (id INTEGER PRIMARY KEY, filename TEXT UNIQUE)''')
c=conn.cursor().execute('''CREATE TABLE IF NOT EXISTS playlist (id INTEGER PRIMARY KEY, song_id INTEGER, played BOOLEAN, timestamp TIMESTAMP, nick TEXT)''')
conn.commit()
conn.close()

def find(phenny, input):
	sWords = re.sub("\.find\ ?", "", input).split(" ")

	searchWords = []

	for word in sWords:
		searchWords.append("%" + word + "%")

	if len(searchWords) < 1:
		phenny.write(('PRIVMSG', input.nick), "Search query must be 3 or more characters")
		return

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

	retStr = "Results for search: " + (" ").join(sWords)
	phenny.write(('PRIVMSG', input.nick), retStr)

	for row in c:
		phenny.write(('PRIVMSG', input.nick), str(row[0]) + ": " + os.path.basename(str(row[1])))
		time.sleep(.5)

	cn.close()
	
find.commands = ['find']
find.priority = 'medium'

def rebuild_cache(phenny, input):
	files = get_cdg_files(CDG_DIR)
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	phenny.say("Updating cache for " + str(len(files)) + " files...")
	for file in files:
		c = cn.cursor().execute("""INSERT OR IGNORE INTO songs (filename) VALUES (?);""", [file])
		cn.commit()	
	cn.close()

rebuild_cache.commands = ['rebuild_cache']
rebuild_cache.priority = 'medium'

def play(phenny, input):
	args = re.sub("\.play\ ?", "", input).split(" ")
	cn = sqlite3.connect(SQLITE_DB)
	cn.text_factory = str
	c = cn.cursor().execute("""SELECT filename, id FROM songs WHERE id = ?;""", [args[0]])
	res = c.fetchone()
	playFile = str(res[0])
	playId = str(res[1])

	phenny.say("Queueing file: " + playFile)
	now = datetime.datetime.now()
	cn.cursor().execute("""INSERT INTO playlist ( timestamp, nick, song_id, played ) VALUES ( ?, ?, ?, ? )""", [ now, "adam[0]", playId, 0] )
	cn.commit()
	cn.close()
	

play.commands = ['play']
play.priority = 'medium'

def get_cdg_files(dir):
	basedir = dir
	subdirlist = []
	file_list = []
	for f in os.listdir(dir):
		if os.path.isfile(dir + "/" + f):
			if f.endswith(".cdg"):
				file_list.append(dir + "/" + f)		
		else:
			subdirlist.append(os.path.join(basedir, f))

	for subdir in subdirlist:
		for file in get_cdg_files(subdir):
			file_list.append(file)

	return file_list

def setup(phenny): 
	def monitor(phenny): 

		cn = sqlite3.connect(SQLITE_DB)
		time.sleep(5)
		while True: 
			c=cn.cursor().execute('''SELECT songs.filename, playlist.id FROM PLAYLIST INNER JOIN songs ON song_id = songs.id WHERE playlist.played = 0 ORDER BY timestamp LIMIT 1;''')
			res = c.fetchone()
			if (res != None):
				cn.cursor().execute('''UPDATE playlist set played = 1 WHERE id = ?;''', [ res[1] ])
				cn.commit()
				phenny.msg("#hive76", "Playing: " + str(res[0]))
				playCMD = PYCDG_PATH + '/pycdg.py'
				subprocess.call(["python", playCMD, "-w 800", "-h 600", res[0]])
				phenny.msg("#hive76", "Done playing: " + str(res[0]))
				time.sleep(10)

			time.sleep(5)

	targs = (phenny,)
	t = threading.Thread(target=monitor, args=targs)
	t.start()
	

if __name__ == '__main__':
	find(None, 'all')

