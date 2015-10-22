# import xbmcplugin
# import xbmcvfs
import xbmc
import xbmcgui
import xbmcaddon
import requests
import re
import time
import threading
import CacheStorage
from bs4 import BeautifulSoup, SoupStrainer


__addon_id__ = "plugin.video.cinemassacre_redux"

cache = CacheStorage.CacheStorage(__addon_id__, 1) # (Your plugin name, Cache time in hours)

__Addon__ = xbmcaddon.Addon(__addon_id__)
__cwd__ = __Addon__.getAddonInfo('path')
__mainwindowxml__ = 'main_window.xml'
__mainurl__ = 'http://cinemassacre.com/'
__nextpage__ = 'http://cinemassacre.com/wp-admin/admin-ajax.php'
__nextpage_data__ = {
    'action':'infinite_scroll',
    'page_no':0,
    'cat':0,
    'loop_file':'loop'
    }

ACTION_MOUSE_WHEEL_UP = 104
ACTION_MOUSE_WHEEL_DOWN = 105
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_PAGE_UP = 5
ACTION_PAGE_DOWN = 6
MOVE_ACTIONS = [
    ACTION_MOUSE_WHEEL_UP, ACTION_MOUSE_WHEEL_DOWN, ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT,
    ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_PAGE_UP, ACTION_PAGE_DOWN
    ]

NAVBAR_CONTROL = 1001
VIDLIST_CONTROL = 1002

request_headers = {'user-agent': 'Mozilla/5.0 ;Windows NT 6.1; WOW64; Trident/7.0; rv:11.0; like Gecko'}

'''
class Player(xbmc.Player):
    def onPlayBackEnded(self, *args, **kwargs):
        pass
    def onPlayBackStopped(self, *args, **kwargs):
        pass
    def onPlayBackStarted(self, *args, **kwargs):
        pass
    def play(self, *args, **kwargs):
        if 'gui' in kwargs:
            self.gui = kwargs['gui']

        pass
'''

class ASync(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.__result = None
        self.__target = None
        self.__args = []
        self.__kwargs = {}
        if 'target' in kwargs:
            self.__target = kwargs['target']
        if 'args' in kwargs:
            self.__args = kwargs['args']
        if 'kwargs' in kwargs:
            self.__kwargs = kwargs['kwargs']
        threading.Thread.__init__(self, *args, **kwargs)

    def run(self):
        try:
           if self.__target:
                self.__result = self.__target(*self.__args, **self.__kwargs)
        finally:
            del self.__target, self.__args, self.__kwargs

    def join(self):
        threading.Thread.join(self)
        return self.__result

class ReqCache(object):
    def get(self, url, headers=None):
        if headers == None:
            headers = request_headers
        cached = cache.get(url)
        if cached:
            return cached.decode('hex')
        ret = requests.get(url, headers=headers)
        cache.set(url, ret.text.encode('utf-8').encode('hex'))
        return ret.text

    def post(self, url, data=None, headers=None):
        if headers == None:
            headers = request_headers
        _str = '&'.join('%s=%s' % (f,g) for f,g in data.iteritems())
        # cache.delete(url+'?'+_str)
        cached = cache.get(url+'?'+_str)
        if cached:
            return cached.decode('hex')
        ret = requests.post(url, data=data, headers=headers)
        cache.set(url+'?'+_str, ret.text.encode('utf-8').encode('hex'))
        return ret.text

reqcache = ReqCache()

class Cinemasscre(xbmcgui.WindowXMLDialog):
    def get_videos(self, url, req=None):
        if not req:
            req = reqcache.get(url, headers=request_headers)

        if url == __mainurl__:
            self.cur_page = 0
            self.cur_total_page = 0
            self.cur_cat = 0
            vids = BeautifulSoup(req, 'html.parser', parse_only = SoupStrainer('div', id=re.compile('custom-recent-posts')))
            items = vids.find('div').findAll('div', class_='listitem', recursive=False)
        else:
            scripts = BeautifulSoup(req, 'html.parser', parse_only = SoupStrainer('script'))
            self.cur_page = 0
            self.cur_total_page = 0
            self.cur_cat = 0
            for a in scripts:
                if re.search('.*loadArticle.*', a.getText()):
                    self.cur_page = int(re.search('var count = (\d*);', a.getText()).group(1))
                    self.cur_total_page = int(re.search('var total = (\d*);', a.getText()).group(1))
                    self.cur_cat = int(re.search('var cat = (\d*);', a.getText()).group(1))
                    break
            print 'url: %s page: %s total: %s cat: %s' % (url, self.cur_page, self.cur_total_page, self.cur_cat)
            self.cache_next_page()
            vids = BeautifulSoup(req, 'html.parser', parse_only = SoupStrainer('div', id='postlist'))
            items = vids.findAll('div', class_='archiveitem')

        return self.parse_vid_list(items)

    def parse_vid_list(self, items):
        videos = []
        for item in items:
            img = item.find('img').get('src')
            href = item.find('a').get('href')
            print [item.getText()]
            listitem = xbmcgui.ListItem( label=item.getText().strip() ) 
            listitem.setProperty('url', href)
            listitem.setIconImage(img)
            videos.append(listitem)
        return videos

    def cache_next_page(self):
        if self.cur_page > self.cur_total_page or self.cur_total_page == 0:
            print 'no %s %s' % (self.cur_page, self.cur_total_page)
            return
        self.active_cache_worker = True
        data_post = __nextpage_data__.copy()
        data_post['page_no'] = self.cur_page
        data_post['cat'] = self.cur_cat
        self.cur_page = self.cur_page + 1

        '''
        vid_list = self.getControl(VIDLIST_CONTROL)
        listitem = xbmcgui.ListItem( label='Loading Extra Videos' ) 
        listitem.setIconImage('loading_circle.gif')
        vid_list.addItem(listitem)
        '''
        req = self.funcWithDialog(reqcache.post, __nextpage__, data=data_post, headers=request_headers, bg=True)
        # req = reqcache.post(__nextpage__, data=data_post, headers=request_headers)

        vids = BeautifulSoup(req, 'html.parser', parse_only = SoupStrainer('div', class_='archiveitem'))
        self.cached_next_page = self.parse_vid_list(vids)
        self.active_cache_worker = False
        self.active_cache_worker_list = []

    def get_video_url(self, url):

        page = self.funcWithDialog(reqcache.get, url, message='Downloading', line1='Getting Video')
        vids = BeautifulSoup(page, 'html.parser', parse_only = SoupStrainer('div', class_='videoarea'))
        img = vids.find('script').get('src')
        page = self.funcWithDialog(reqcache.get, img, message='Downloading', line1='Getting Video')
        server = re.search('var SWMServer = [\'\"]([^\'\"]+?)[\'\"];', page).group(1)
        vidid = re.search('[\'\"]vidid[\'\"]:  [\'\"]([^\'\"]+?)[\'\"],', page).group(1)
        _url = 'http://%s/vod/smil:%s.smil/playlist.m3u8' % (server, vidid)
        _playlist = reqcache.get(_url)
        _vid = ''
        for _line in _playlist.splitlines():
            if _line.startswith(vidid):
                _vid = _line.replace('_chunk.m3u8', '')
                _vid = _vid.replace('__', '_')
                break
        _url = 'http://%s/vod/%s' % (server, _vid)
        '''
        _urlb = 'http://%s/vod/%s_hd1.mp4' % (server, vidid)
        '''
        player = xbmc.Player()
        player.play(_url)
        self.close()
        while player.isPlaying():
            pass
        self.doModal()
        return

    def onClick(self, controlID):
        print 'onClick: %s' % controlID
        _control = self.getControl(controlID)
        if controlID == NAVBAR_CONTROL:
            selected = _control.getSelectedItem()
            _url = selected.getProperty('url')

            videos = self.funcWithDialog(self.get_videos, _url)
            vid_list = self.getControl(VIDLIST_CONTROL)
            vid_list.reset()
            vid_list.addItems(videos)

        elif controlID == VIDLIST_CONTROL:
            selected = _control.getSelectedItem()
            _url = selected.getProperty('url')
            video_url = self.get_video_url(_url)

            pass

    def onAction(self, actionID):
        xbmcgui.WindowXMLDialog.onAction(self, actionID)
        if actionID.getId() in MOVE_ACTIONS and not self.active_cache_worker:
            vid_list = self.getControl(VIDLIST_CONTROL)
            if vid_list.getSelectedPosition() > vid_list.size()-10:
                cur_pos = vid_list.getSelectedPosition()
                vid_list.addItems(self.cached_next_page)
                vid_list.selectItem(cur_pos)
                self.cached_next_page = []
                worker = ASync(target=self.cache_next_page)
                worker.start()
                self.active_cache_worker_list.append(worker)
                # self.cache_next_page()

    def funcWithDialog(self, func, *args, **kwargs):
        _bg = False
        _message = 'Loading'
        _line1 = 'Getting Video List'

        if 'bg' in kwargs:
            _bg = kwargs['bg']
            del kwargs['bg']

        if 'message' in kwargs:
            _message = kwargs['message']
            del kwargs['message']

        if 'line1' in kwargs:
            _line1 = kwargs['line1']
            del kwargs['line1']

        if _bg:
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create('Loading Next Video Page')
        else:
            pDialog = xbmcgui.DialogProgress()
            pDialog.create(_message, _line1)
            
        start_time = time.time()
        worker = ASync(target=func, args=args, kwargs=kwargs)
        worker.start()
            
        lasttime = 0
        percent = 5
        percent_add = 5
        while worker.isAlive():
            if time.time() > lasttime + 1:
                lasttime = time.time()
                elapsed = lasttime - start_time + 1
                xx = int((elapsed * elapsed) / 100)
            if xx < 100:
                if xx < 1:
                    xx = 1
                pDialog.update(xx)
        pDialog.close()
        return worker.join()

    def onInit( self ):
        if hasattr(self, 'doneInit'):
            return

        self.cur_page = 0
        self.cur_total_page = 0
        self.cur_cat = 0
        self.cached_next_page = []
        self.active_cache_worker = False
        self.active_cache_worker_list = []

        nav_list = self.getControl(NAVBAR_CONTROL)
        vid_list = self.getControl(VIDLIST_CONTROL)
        
        listitem = xbmcgui.ListItem( label='Latest' ) 
        listitem.setProperty('url', __mainurl__)
        navbar_items = [listitem]

        r = self.funcWithDialog(reqcache.get, __mainurl__, headers=request_headers)

        navbar = BeautifulSoup(r, 'html.parser', parse_only = SoupStrainer('div', id='navArea'))
        _li = navbar.find('ul').findAll('li', recursive=False)
        for _li_a in _li:
            if _li_a.find('a').getText().lower() != 'site':
                _li_b = _li_a.find('ul').findAll('li', recursive=False)
                for _li_c in _li_b:
                    a_el = _li_c.find('a')
                    text = a_el.getText()
                    href = a_el.get('href')
                    listitem = xbmcgui.ListItem( label=text ) 
                    listitem.setProperty('url', href)
                    navbar_items.append(listitem)

        nav_list.addItems(navbar_items)
        self.setFocus(nav_list)

        videos = self.get_videos(url=__mainurl__, req=r)
        vid_list.addItems(videos)
        self.doneInit = True
        

if __name__ == '__main__':
    plugin = Cinemasscre(__mainwindowxml__ , __cwd__, 'default')
    plugin.doModal()
    del plugin
    # cache.set('test','test')
    # print cache.get('test')
    # cache.delete('test')
    # print cache.get('test')

