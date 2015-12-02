# Include the Dropbox SDK
import dropbox
import time
import datetime
import urllib
import os,sys
import ConfigParser
import os.path
import shutil
import subprocess
import libtorrent as lt
import thread
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Get your app key and secret from the Dropbox developer website

class Otto:
	APP_KEY = ''
	APP_SECRET = '' 
	ACCESS_TOKEN = ''
	DOWNLOAD_LIMIT = 1024000
	CHECK_DELAY = 60 #number of seconds before checking dropbox for updates
	CUR_REV = 0
	TORRENT_DIR = ''
	MOVIE_DIR = 'movies'
	TV_DIR = 'tv'
	LOGFILE = ''
	LOGNAME = ''
	ERRFILE = ''
	ERRNAME = ''
	client = None
	config = None



	def getFile(self):
		"""
		Pull file from dropbox and assess if needs to be processed
		"""
		folder_metadata = self.client.metadata('/')
		if False:
			print "File Listings:"
			for item in folder_metadata['contents']:
				if not item['is_dir']:
					print item['path']

		f, metadata = self.client.get_file_and_metadata('/commands.conf')
		read_rev = metadata['revision']
		
		if read_rev > self.CUR_REV:
			self.logger.info("[Processing rev "+str(read_rev)+"]")
			self.CUR_REV = read_rev
			self.processConf(f.read())
		else:
			self.logger.info("... nothing to do")


	def authorise(self):
		"""
		Authorise against dropbox and return access token
		"""
		flow = dropbox.client.DropboxOAuth2FlowNoRedirect(self.APP_KEY, self.APP_SECRET)

		# Have the user sign in and authorize this token
		authorize_url = flow.start()
		print '1. Go to: ' + authorize_url
		print '2. Click "Allow" (you might have to log in first)'
		print '3. Copy the authorization code.'
		code = raw_input("Enter the authorization code here: ").strip()
		# This will fail if the user enters an invalid authorization code
		access_token, user_id = flow.finish(code)
		return access_token

	def processConf(self,content):
		"""
		Iterate through the pulled down config file
		"""
		try:
			lines = content.split('\n')
			for line in lines:
				self.logger.info("[Processing] " + str(line))
				try:
					command,arg = line.split(' ',1)
				except:
					command = line
					arg = ''
				self.logger.info("[Command] "+command)
				self.logger.info("[Arg] "+arg)
				command = command.lower().strip()
				if command == 'tor': 
					self.processTorrent(arg)
				elif command == 'com':
					self.processCom(arg)
				elif command == 'mag':
					thread.start_new_thread( self.downloadMagnet, (arg, ) )
				elif command == 'log':
					self.getLog();
				elif command == 'exit':
					sys.exit(0)
				elif command == 'reload':
					self.readConfig(configfile)
				elif command == 'magtv':
					thread.start_new_thread( self.downloadMagnet, (arg, 'tv',) )
				elif command == 'magmovie':
					thread.start_new_thread( self.downloadMagnet, (arg, 'movie',) )
				elif command == 'setdelay':
					try:
						self.CHECK_DELAY = int(arg)
					except:
						self.logger.error("Problem setting delay")
						self.CHECK_DELAY = 180
		except Exception as e:
			self.logger.error(traceback.format_exc())


	def getLog(self):
		"""
		Pushes log file to dropbox
		"""
		try:
			f = open(self.LOGFILE, 'rb')
			try:
				self.client.put_file('/log_otto.log', f, overwrite=True, )
				self.logger.info("marking sendlog as done")
			except Exception as ex:
				self.logger.error("problem sending log, known openssl issue " +str(ex))
			f.close()
		except Exception as e:
			self.logger.error(e)
			self.logger.error(traceback.format_exc())

	def processCom(self,arg):
		"""
		Process command name and validate it is a valid command, if not, then log, but ignore
		"""
		arg = arg.strip()
		self.logger.info( "[Looking for command] "+str(arg))
		try:
			if not self.config.has_option('commands',arg):
				self.logger.info("[INVALID OPTION] Command '"+str(arg)+"'' was attempted to be run")
				return
			p = subprocess.Popen(self.config.get('commands',arg), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
			output, err = p.communicate()
			
			self.logger.info( "[Output] "+ str(output))	
			self.logger.info( "[Err]" + str(err))
			# self.logger.info(subprocess.check_output(args,shell=True))

		except Exception as e:
			self.logger.error(traceback.format_exc())



	def processTorrent(self,torrent_url):
		"""
		Downloads the .torrent file to the specified directory
		"""
		try:
			self.logger.info( "[Downloading torrent... "+str(torrent_url) + "]")
			testfile = urllib.URLopener()
			fh, headers = testfile.retrieve(torrent_url)
			filename = os.path.split(fh)[1]
			dest = os.path.join(self.TORRENT_DIR,filename)
			shutil.move(fh, dest)
			# print str(fh)
			self.logger.info( "[Complete 1/2] Torrent download Completed to "+str(dest))
			thread.start_new_thread( self.downloadTorrent, (dest, ) )
		except Exception as e:
			self.logger.error(traceback.format_exc())

	def execute(self):
		"""
		Loop to run program
		Sets up torrent session also
		"""
		try:
			self.ses = lt.session()
			self.logger.info("Setting download limit to "+str(self.DOWNLOAD_LIMIT)+ " bytes")
			self.ses.set_download_rate_limit(self.DOWNLOAD_LIMIT)

			self.client = dropbox.client.DropboxClient(self.ACCESS_TOKEN)
			print "Otto is now running, log file can be found here: "+str(self.LOGFILE)

			f = open(configfile, 'rb')
			try:
				self.client.put_file('/available_commands', f, overwrite=True, )
				self.logger.info("available commands sent")
			except Exception as ex:
				self.logger.error("problem trying to send available commands")
				self.logger.error(ex)
			f.close()
			while True:
				self.client = dropbox.client.DropboxClient(self.ACCESS_TOKEN)
				st = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
				self.logger.info( str(st) + " checking dropbox...")
				otto.getFile()
				time.sleep(self.CHECK_DELAY)
		except Exception as e:
			self.logger.error(traceback.format_exc())

	def firstTimeWizard(self,configfile):
		"""
		This gets directory info from user and also 
		guides user through authorising dropbox access
		"""
		
		if os.path.exists(configfile):
			print 'Using config file '+str(configfile)
			return True
		print "script dir = "+str(scriptdir)

		config = ConfigParser.RawConfigParser()
		config.add_section('dirs')
		config.add_section('dropbox')
		config.add_section('misc')
		config.add_section('commands')

		config.set('misc', 'checkfrequency', 30)
		config.set('misc', 'downloadlimit', 1024000)
		config.set('commands', '1', 'ps -ef')

		while self.APP_KEY == '':
			self.APP_KEY = raw_input("Enter Dropbox App Key: ").strip()
		config.set('dropbox', 'appkey', self.APP_KEY)

		while self.APP_SECRET == '':
			self.APP_SECRET = raw_input("Enter Dropbox App Secret: ").strip()
		config.set('dropbox', 'appsecret', self.APP_SECRET)

		self.ACCESS_TOKEN = self.authorise()
		if not self.ACCESS_TOKEN:
			print "Access token not received, exiting..."
			return False

		config.set('dropbox', 'accesstoken', self.ACCESS_TOKEN)
		print 'Access Token: '+str(self.ACCESS_TOKEN) + ' saved to config'

		torrentdir = raw_input("Enter torrent download dir:["+str(scriptdir)+"] ").strip()
		if not os.path.isdir(torrentdir):
			torrentdir = os.path.join(scriptdir,'torrents')
		config.set('dirs', 'torrentdir', torrentdir)

		# Writing our configuration file to 'example.cfg'
		with open(configfile, 'wb') as theconfigfile:
			config.write(theconfigfile)
		return True

	def downloadMagnet(self,magnetlink,location=''):
		try:
			savepath = self.TORRENT_DIR
			if len(location)>0:
				savepath = os.path.join(savepath, location)
				if not os.path.exists(savepath):
					os.makedirs(savepath)
					self.logger.info("Created directory "+str(savepath)) 
			params = { 'save_path': savepath}
			handle = lt.add_magnet_uri(self.ses, magnetlink, params)

			self.logger.info( 'downloading metadata...')
			while (not handle.has_metadata()): time.sleep(1)
			self.logger.info( 'got metadata, starting torrent download...')
			while (handle.status().state != lt.torrent_status.seeding):
				self.logger.info(handle.name()+ ":  "+ str(handle.status().download_rate/1000)+ "kb/s : "+str(handle.status().upload_rate/1000)+"kb/s. " + str(handle.status().progress*100)+"%%")
				self.logger.info("Tracker: "+ handle.status().current_tracker + " Seeds: "+str(handle.status().num_seeds)+ " Peers: "+str(handle.status().num_peers))
				time.sleep(10)
			self.logger.info( "[Complete] Download complete of "+handle.name())
			try:
				self.logger.info("Removing torrent: "+str(handle.name()))
				self.ses.remove_torrent(handle)
			except Exception as ee:
				self.logger.error(traceback.format_exc())
		except Exception as e:
			self.logger.error(traceback.format_exc())



	def downloadTorrent(self,torrentfile):
		"""
		Download the files the torrent is pointing at
		"""
		try:
			self.ses.listen_on(6881, 6891)

			e = lt.bdecode(open(torrentfile, 'rb').read())
			info = lt.torrent_info(e)

			params = { 'save_path': self.TORRENT_DIR, \
				'storage_mode': lt.storage_mode_t.storage_mode_sparse, \
				'ti': info }
			h = self.ses.add_torrent(params)

			s = h.status()
			while (not s.is_seeding):
				s = h.status()

				state_str = ['queued', 'checking', 'downloading metadata', \
				        'downloading', 'finished', 'seeding', 'allocating']
				self.logger.info( '%.2f%% complete (down: %.1f kb/s up: %.1f kB/s peers: %d) %s' % \
				        (s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, \
				        s.num_peers, state_str[s.state]))

				time.sleep(10)
			self.logger.info( "[Complete 2/2] Torrent download Completed")
			self.ses.remove_torrent(h)
			os.remove(torrentfile)
		except Exception as e:
			self.logger.error(traceback.format_exc())

	def readConfig(self,configfile):
		"""
		Reads configuration from commands.conf at startup
		"""
		try:
			self.config = ConfigParser.RawConfigParser()
			self.config.read(configfile)
			self.ACCESS_TOKEN = self.config.get('dropbox','accesstoken')
			self.TORRENT_DIR = self.config.get('dirs','torrentdir')
			self.CHECK_DELAY = self.config.getint('misc','checkfrequency')
			self.DOWNLOAD_LIMIT = self.config.getint('misc','downloadlimit')
		except Exception as e:
			print e

	def setupLogger(self):
		"""
		Setup logger and logger properties
		"""
		self.logger = logging.getLogger(__name__)
		self.logger.setLevel(logging.INFO)
		self.LOGNAME = "otto_"+self.ACCESS_TOKEN+".log"
		self.LOGFILE = os.path.join(scriptdir,self.LOGNAME)
		
		self.ERRNAME = "error_otto_"+self.ACCESS_TOKEN+".log"
		self.ERRFILE = os.path.join(scriptdir,self.ERRNAME)

		# handler = logging.FileHandler(self.LOGFILE)
		handler = RotatingFileHandler(self.LOGFILE, maxBytes=100000,backupCount=5)
		handler.setLevel(logging.INFO)
		errhandler = RotatingFileHandler(self.ERRFILE, maxBytes=100000,backupCount=5)
		errhandler.setLevel(logging.ERROR)
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		handler.setFormatter(formatter)
		errhandler.setFormatter(formatter)
		self.logger.addHandler(handler)
		self.logger.addHandler(errhandler)
		
scriptdir = os.path.dirname(os.path.realpath(__file__))
configfile = os.path.join(scriptdir,'otto.conf')
otto = Otto()
if otto.firstTimeWizard(configfile):
	otto.readConfig(configfile)
	otto.setupLogger()
	otto.execute()


