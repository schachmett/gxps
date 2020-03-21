# This windows building routine was largely adopted from the
# Quod Libet project 
# https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

"""This file gets edited at build time to add build specific data"""

BUILD_TYPE = u"default"
"""Either 'windows', 'windows-portable' or 'default'"""

BUILD_INFO = u""
"""Additional build info like git revision etc"""

BUILD_VERSION = 0
"""1.2.3 with a BUILD_VERSION of 1 results in 1.2.3.1"""
