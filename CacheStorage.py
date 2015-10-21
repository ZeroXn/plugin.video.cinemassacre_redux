import sys
import os
import time
import inspect
try: import sqlite
except: pass
try: import sqlite3
except: pass

class CacheStorage(object):
    def __init__(self, plugin_id, timeout=12):
        
        if hasattr(sys.modules["__main__"], "xbmc"):
            self.xbmc = sys.modules["__main__"].xbmc
        else:
            import xbmc
            self.xbmc = xbmc

        if hasattr(sys.modules["__main__"], "xbmcvfs"):
            self.xbmcvfs = sys.modules["__main__"].xbmcvfs
        else:
            import xbmcvfs
            self.xbmcvfs = xbmcvfs

        if hasattr(sys.modules["__main__"], "xbmcaddon"):
            self.xbmcaddon = sys.modules["__main__"].xbmcaddon
        else:
            import xbmcaddon
            self.xbmcaddon = xbmcaddon

        self.modules = sys.modules

        self.path = self.xbmc.translatePath('special://temp/%s' % plugin_id)
        if not self.xbmcvfs.exists(self.path):
            self.xbmcvfs.mkdir(self.path)
        self.path = os.path.join(self.path, 'commoncache.db')

        self.sql3 = False
        self.sql2 = False
        self.conn = False
        if "sqlite3" in self.modules:
            self.sql3 = True
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.curs = self.conn.cursor()
        elif "sqlite" in self.modules:
            self.sql2 = True
            self.conn = sqlite.connect(self.path)
            self.curs = self.conn.cursor()

        self.CacheTimeout = timeout * 3600
        self.table = 'cache'
        self.plugin = plugin_id

    def _log(self, description, level=0):
        try:
            self.xbmc.log(u"[%s] %s : '%s'" % (self.plugin, repr(inspect.stack()[1][3]), description), self.xbmc.LOGNOTICE)
        except:
            self.xbmc.log(u"[%s] %s : '%s'" % (self.plugin, repr(inspect.stack()[1][3]), repr(description)), self.xbmc.LOGNOTICE)

    def _sqlExecute(self, sql, data):
        try:
            if self.sql2:
                self.curs.execute(sql, data)
            elif self.sql3:
                sql = sql.replace("%s", "?")
                if isinstance(data, tuple):
                    self.curs.execute(sql, data)
                else:
                    self.curs.execute(sql, (data,))
        except sqlite3.DatabaseError, e:
            if self.xbmcvfs.exists(self.path) and (str(e).find("file is encrypted") > -1 or str(e).find("not a database") > -1):
                self._log(u"Deleting broken database file")
                self.xbmcvfs.delete(self.path)
            else:
                self._log(u"Database error, but database NOT deleted: " + repr(e))
        except:
            self._log(u"Uncaught exception")

    def _checkTable(self, table):
        try:
            self.curs.execute("create table " + table + " (name text unique, data text)")
            self.conn.commit()
            self._log(u"Created new table")
        except:
            self._log(u"Passed", 5)
            pass

    def _sqlSet(self, table, name, _data):
        data = repr({'data':_data, '__timeout__':time.time()})
        self._log(name + str(repr(data))[0:20], 2)

        self._checkTable(table)
        if self._sqlGet(table, name).strip():
            self._log(u"Update : " + data.decode('utf8', 'ignore'), 3)
            self._sqlExecute("UPDATE " + table + " SET data = %s WHERE name = %s", (data, name))
        else:
            self._log(u"Insert : " + data.decode('utf8', 'ignore'), 3)
            self._sqlExecute("INSERT INTO " + table + " VALUES ( %s , %s )", (name, data))

        self.conn.commit()
        self._log(u"Done", 2)
        return ""

    def _sqlDel(self, table, name):
        self._log(name + u" - " + table, 1)

        self._checkTable(table)

        self._sqlExecute("DELETE FROM " + table + " WHERE name LIKE %s", name)
        self.conn.commit()
        self._log(u"done", 1)
        return "true"

    def _sqlGet(self, table, name):
        self._log(name + u" - " + table, 2)

        self._checkTable(table)
        self._sqlExecute("SELECT data FROM " + table + " WHERE name = %s", name)

        for row in self.curs:
            self._log(u"Returning : " + str(repr(row[0]))[0:20], 3)
            _row = eval(row[0])
            if '__timeout__' not in _row:
                break
            if time.time()-self.CacheTimeout > _row['__timeout__']:
                self.delete(name)
                break
            return _row['data']

        self._log(u"Returning empty", 3)
        return " "

    def delete(self, name):
        self._log(name, 1)
        if self.conn:
            self._sqlDel(self.table, name)

    def set(self, name, data):
        self._log(name, 1)
        if self.conn:
            self._sqlSet(self.table, name, data)

    def get(self, name):
        self._log(name, 1)
        if self.conn:
            ret = self._sqlGet(self.table, name)
            try: ret = ret.strip()
            except: pass
            return ret
