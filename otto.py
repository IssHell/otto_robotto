import time
from datetime import datetime
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
from threading import Thread
import telepot
import feedparser

class Otto:
    DOWNLOAD_LIMIT = 1024000
    CHECK_DELAY = 10
    TORRENT_DIR = ''
    LOGFILE = ''
    LOGNAME = ''
    ERRFILE = ''
    ERRNAME = ''
    config = None
    telegram_token = None
    bot = None
    current_responder = None
    feed_url = None
    download_names = {}
    download_links = {}

    def list_new_shows(self):
        """
        use showrss.info for this option
        """
        d = feedparser.parse(self.feed_url)
        total_string = ""
        self.download_names = {}
        self.download_links = {}
        count = 0
        messages = []
        for entry in d.entries:
            count = count + 1
            self.download_names[str(count)] = entry['summary_detail']['value']
            self.download_links[str(count)] = entry['links'][0]['href']
            # would be nice to include date in this message too
            # self.send_message('{}. {}'.format(count, entry['summary_detail']['value']))
            message = '{}. {} {}'.format(count, entry['summary_detail']['value'], entry['published'])
            messages.insert(0, message)
        for m in messages:
            self.send_message(m)



    def get_show_link(self, showname):
        """
        use showrss.info for this option
        """
        thread.start_new_thread(self.downloadMagnet, (self.download_links[showname], 'tv',))
        self.send_message('{} download queued.'.format(self.download_names[showname]))
        return
            

    def process_conf(self,content):
        """
        Iterate through the pulled down config file
        """
        try:
            self.logger.info("received message: {}".format(content))
            try:
                command, arg = content.split(' ', 1)
            except Exception, e:
                command = content
                arg = ''
            self.logger.info("[Command: "+command+"]")
            self.logger.info("[Arg: "+arg+"]")
            command = command.lower().strip()
            if command == 'tor':
                self.processTorrent(arg)
            elif command == 'shows':
                self.list_new_shows()
            elif command == 'show':
                self.get_show_link(arg)
            elif command == 'help':
                self.send_config()
            elif command == 'com':
                self.processCom(arg)
            elif command == 'mag':
                thread.start_new_thread(self.downloadMagnet, (arg, ))
            elif command == 'log':
                self.getLog()
            elif command == 'exit':
                self.logger.info("Quitting Otto as commanded...")
                sys.exit(0)
            elif command == 'reload':
                self.readConfig(configfile)
            elif command == 't':
                thread.start_new_thread(self.downloadMagnet, (arg, 'tv',))
                self.send_message("Magnet download is now queued as TV.")
            elif command == 'm':
                thread.start_new_thread(self.downloadMagnet, (arg, 'movies',))
                self.send_message("Magnet download is now queued as Movie.")
            else:
                self.logger.info("Command not recognised, nothing to do")
        except Exception as e:
            self.logger.error(traceback.format_exc())


    def getLog(self):
        """
        Pushes log file to user
        """
        try:
            f = open(self.LOGFILE, 'rb')
            try:
                log_string = f.read()
                self.send_message(log_string[-3000:])
                self.logger.info("marking sendlog as done")
            except Exception as ex:
                self.logger.error("problem sending log, known openssl issue " +str(ex))
            f.close()
        except Exception as e:
            self.logger.error(e)
            self.logger.error(traceback.format_exc())


    def send_config(self):
        """
        Pushes config file to user
        """
        try:
            f = open(configfile, 'rb')
            try:
                content = f.read()
                self.send_message(content)
                self.logger.info("sent config")
            except Exception as ex:
                self.logger.error("problem sending config, known openssl issue " +str(ex))
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
            self.logger.info( "[Output: "+ str(output)+"]")
            self.logger.info( "[Err:" + str(err)+"]")
            # self.logger.info(subprocess.check_output(args,shell=True))
            self.send_message("Command finished: output [{}] - error [{}]".format(output, err))

        except Exception as e:
            self.logger.error(traceback.format_exc())

    def send_message(self, message):
        self.bot.sendMessage(self.current_responder, message)

    def handle_message(self, msg):
        self.current_responder = msg['from']['id']
        message = msg['text']
        if message.lower() == 'hello otto':
            self.send_message("Hello to you too!")
        else:
            self.process_conf(message)

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
            print "Otto is now running, log file can be found here: "+str(self.LOGFILE)
            self.bot = telepot.Bot(self.telegram_token)
            self.bot.message_loop(self.handle_message)
            while self.RUNAPP:
                time.sleep(self.CHECK_DELAY)
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error('Exiting Otto due to exception...')

    def firstTimeWizard(self,configfile):
        """
        Sets up app
        """

        if os.path.exists(configfile):
            print 'Using config file '+str(configfile)
            return True
        print "script dir = "+str(scriptdir)

        config = ConfigParser.RawConfigParser()
        config.add_section('dirs')
        config.add_section('misc')
        config.add_section('commands')

        config.set('misc', 'checkfrequency', 10)
        config.set('misc', 'downloadlimit', 1024000)
        config.set('commands', '1', 'ps -ef')

        while self.telegram_token == '':
            self.telegram_token = raw_input("Enter telegram token: ").strip()
        config.set('misc', 'telegram_token', self.telegram_token)

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
                try:
                    percentComplete = int(handle.status().progress*100)
                except:
                    percentComplete = handle.status().progress*100
                self.logger.info("DL " + handle.name()+ " ["+ str(handle.status().download_rate/1000)+"kb/s : "+str(handle.status().upload_rate/1000)+"kb/s.] [" + str(percentComplete)+"%]" + " [S:"+str(handle.status().num_seeds)+ " P:"+str(handle.status().num_peers)+"]" )
                time.sleep(10)
            self.logger.info( "[Complete] Download complete of "+handle.name())
            self.send_message('{} completed'.format(handle.name()))
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
        Reads configuration from otto.conf at startup
        """
        try:
            self.config = ConfigParser.RawConfigParser()
            self.config.read(configfile)
            self.CHECK_DELAY = self.config.getint('misc','checkfrequency')
            self.DOWNLOAD_LIMIT = self.config.getint('misc','downloadlimit')
            self.telegram_token = self.config.get('misc','telegram_token')
            self.TORRENT_DIR = self.config.get('dirs','torrentdir')
            self.feed_url = self.config.get('misc', 'feedurl')
        except Exception as e:
            print e

    def setupLogger(self):
        """
        Setup logger and logger properties
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.LOGNAME = "logotto.log"
        self.LOGFILE = os.path.join(scriptdir,self.LOGNAME)

        self.ERRNAME = "error_otto.log"
        self.ERRFILE = os.path.join(scriptdir,self.ERRNAME)

        handler = RotatingFileHandler(self.LOGFILE, maxBytes=100000,backupCount=5)
        handler.setLevel(logging.INFO)
        errhandler = RotatingFileHandler(self.ERRFILE, maxBytes=100000,backupCount=5)
        errhandler.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s %(message)s')
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
    otto.RUNAPP = True
    otto.execute()
