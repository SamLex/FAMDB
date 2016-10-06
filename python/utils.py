import sqlite3
from datetime import date
from http import cookies

from Crypto.Cipher import AES

sessionGenKey = date.today()

__file = open('folders.config')

# upgrade to actually reading properties
missionMainDir = __file.readline()
missionMainArchive = __file.readline()

missionMakerDir = __file.readline()
missionMakerArchive = __file.readline()


class User:
    def __init__(self, email, permissionLevel, login):
        self.email = email
        self.permissionLevel = permissionLevel
        self.login = login


def getCurrentUser(request):
    C = cookies.SimpleCookie()
    C.load(request.getHeader("cookie"))
    sessionId = C['sessionId'].value

    userId = AES.new(sessionGenKey).decrypt(sessionId)

    conn = sqlite3.connect('famdb.db')
    conn.row_factory = sqlite3.Row

    c = conn.cursor()
    c.execute('''select * from users where id = ?''', [userId])
    user = c.fetchone()
    return User(user['email'], user['permissionLevel'], user['login'])
