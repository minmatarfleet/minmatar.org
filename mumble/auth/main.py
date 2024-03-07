import sys, Ice
import Murmur

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
        print("Authenticating user: {0}".format(name))
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