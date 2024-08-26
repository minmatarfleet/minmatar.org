lpconvert_status = "Unknown"


def set_status(status):
    global lpconvert_status
    lpconvert_status = status


def get_status():
    global lpconvert_status
    return lpconvert_status
