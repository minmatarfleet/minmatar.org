lpconvert_status = "Unknown"

lpconvert_data = ""

lp_type_ids = [
    # 41490,
    # 32006,
    # 32014,
    # 21894,
    # 21896,
    # 21898,
    # 21902,
    # 21904,
    # 21906,
    # 21918,
    # 21922,
    # 21924,
    # 31932,
    # 31928,
    # 31924,
    # 31944,
    # 41212,
    # 41215,
    41218,
    # 33157,
    # 29336,
    # 17713,
    # 72811,
    31890,
    31888,
    31892,
    31894,
]

lp_blueprint_ids = {
    # Blueprint: Item
    33158: 33157,
    72923: 72811,
    29339: 29336,
    17714: 17713,
}


def set_status(status):
    global lpconvert_status
    lpconvert_status = status


def get_status():
    return lpconvert_status


def set_item_data(data):
    global lpconvert_data
    lpconvert_data = data


def get_item_data():
    return lpconvert_data
