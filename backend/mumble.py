import os
import sys

import django
import Ice
import Murmur

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


def get_mumble_access_by_username(username):
    from eveonline.models import (  # pylint: disable=import-outside-toplevel
        EveCharacter,
    )
    from mumble.models import (  # pylint: disable=import-outside-toplevel
        MumbleAccess,
    )

    eve_character = EveCharacter.objects.get(character_name=username)
    if not eve_character:
        return None
    if not eve_character.token:
        return None
    user = eve_character.token.user
    if not user:
        return None
    return MumbleAccess.objects.filter(user=user).first()


class MetaCallback(Murmur.MetaCallback):
    def __init__(self):
        Murmur.MetaCallback()

    def started(self, srv, context=None):
        print("Server started")

    def stopped(self, srv, context=None):
        print("Server stopped")


class Authenticator(Murmur.ServerAuthenticator):
    """
    Custom ICE authenticator for Mumble
    """

    def __init__(self):
        Murmur.ServerAuthenticator.__init__(self)

    def authenticate(
        self, name, pw, certificates, certhash, certstrong, context=None
    ):
        try:
            print(f"Authenticating: {name}")

            if name == "SuperUser":
                return -1, None, None
            mumble_access = get_mumble_access_by_username(name)
            if mumble_access is None:
                print(f"Failed authenticating: {name}")
                return -1, None, None

            if mumble_access.password == pw:
                return mumble_access.user.id, "[FL33T] " + name, None

        except Exception as e:
            print(f"Error authenticating: {name}")
            print(e)
            return -1, None, None

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

    django.setup()
    print("Starting authenticator...")

    ice = Ice.initialize(sys.argv)
    base = ice.stringToProxy("Meta:tcp -h murmur -p 6502")

    meta = Murmur.MetaPrx.checkedCast(base)
    if not meta:
        raise RuntimeError("Invalid Proxy")

    adapter = ice.createObjectAdapterWithEndpoints(
        "Callback.Client", "tcp -h 0.0.0.0 -p 6502"
    )
    adapter.activate()

    server = meta.getServer(1)
    print("Binding to server: {0}".format(server.id()))

    meta_callback_bind = Murmur.MetaCallbackPrx.checkedCast(
        adapter.addWithUUID(MetaCallback())
    )
    meta.addCallback(meta_callback_bind)

    authenticator_bind = Murmur.ServerAuthenticatorPrx.checkedCast(
        adapter.addWithUUID(Authenticator())
    )
    server.setAuthenticator(authenticator_bind)

    ice.waitForShutdown()
    ice.shutdown()
    db.shutdown()
