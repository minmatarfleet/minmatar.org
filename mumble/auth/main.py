import sys, os, Ice, Murmur, mariadb

db = None

class Database:
    def __init__(self):
        self.connection = None
        try:
            self.connection = mariadb.connect(
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASSWORD"],
                host=os.environ["DB_HOST"],
                port=int(os.environ["DB_PORT"]),
                database=os.environ["DB_NAME"],
            )

        except mariadb.Error as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)

        self.cursor = self.connection.cursor()

    def shutdown(self):
        if self.connection:
            self.connection.close()

    def get_mumble_access_by_username(self, username):
        query = """
            SELECT
                mm.*
            FROM
                mumble_mumbleaccess mm
            INNER JOIN esi_token et ON
                et.user_id = mm.user_id 
            INNER JOIN eveonline_eveprimarycharacter ee ON
                ee.character_id = et.character_id
            WHERE et.character_name = ?
            LIMIT 1
        """
        self.cursor.execute(query, (username))
        return self.cursor.fetchone()


class MetaCallback(Murmur.MetaCallback):
    def __init__(self):
        Murmur.MetaCallback()

    def started(self, srv, context=None):
        print("Server started")

    def stopped(self, srv, context=None):
        print("Server stopped")

class Authenticator(Murmur.ServerAuthenticator):
    def __init__(self):
        Murmur.ServerAuthenticator.__init__(self)

    def authenticate(self, name, pw, certificates, certhash, certstrong, context=None):
        print("Authenticating user: {0}/{1}".format(name, pw))

        (mumble_password) = db.get_mumble_access_by_username(name)

        return -1, None, None

    def getInfo(self, id, current=None):
        return False, None

    def nameToId(self, name, current=None):
        return id

    def idToName(self, id, current=None):
        return None

    def idToTexture(self, id, current=None):
        return None

if __name__ == "__main__":
    print("Starting authenticator...")

    db = Database()

    ice = Ice.initialize(sys.argv)
    base = ice.stringToProxy("Meta:tcp -h murmur -p 6502")

    meta = Murmur.MetaPrx.checkedCast(base)
    if not meta:
        raise RuntimeError("Invalid Proxy")

    adapter = ice.createObjectAdapterWithEndpoints("Callback.Client", "tcp -h 0.0.0.0 -p 6502")
    adapter.activate()

    server = meta.getServer(1)
    print("Binding to server: {0}".format(server.id()))

    meta_callback_bind = Murmur.MetaCallbackPrx.checkedCast(adapter.addWithUUID(MetaCallback()))
    meta.addCallback(meta_callback_bind)

    authenticator_bind = Murmur.ServerAuthenticatorPrx.checkedCast(adapter.addWithUUID(Authenticator()))
    server.setAuthenticator(authenticator_bind)

    ice.waitForShutdown()
    ice.shutdown()
    db.shutdown()