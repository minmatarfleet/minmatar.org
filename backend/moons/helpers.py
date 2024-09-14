# 30k m3 per hour from an athanor for base calculation
def get_athanor_yield():
    """
    Return the hourly yield of an Athanor
    """
    return {
        "Hydrocarbons": 65,
        "Pyerite": 6000,
        "Mexallon": 400,
    }


def get_metanox_yield():
    """
    Return the hourly yield of Metanox mining
    40% of the yield of an Athanor
    """
    return {
        "Hydrocarbons": 65,
        "Pyerite": 6000,
        "Mexallon": 400,
    }
