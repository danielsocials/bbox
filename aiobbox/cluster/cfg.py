import os
import re
import time
import json
import sys
from aiobbox.utils import json_pp, json_to_str

class SharedConfig:
    def __init__(self):
        self.sections = {}

    def replace_with(self, newcfg):
        self.sections = newcfg.sections

    def set(self, sec, key, value):
        section = self.sections.setdefault(sec, {})
        section[key] = value

    def delete(self, sec, key):
        section = self.sections.get(sec)
        if section:
            return section.pop(key, None)

    def delete_section(self, sec):
        return self.sections.pop(sec, None)

    def get(self, sec, key, default=None):
        section = self.sections.get(sec)
        if section:
            return section.get(key, default)
        else:
            return default

    def get_chain(self, secs, key, default=None):
        for sec in secs:
            v = self.get(sec, key)
            if v:
                return v
        return default

    def get_strict(self, sec, key):
        return self.sections[sec][key]

    def get_section(self, sec):
        return self.sections.get(sec)

    def get_section_strict(self, sec):
        return self.sections[sec]

    def has_section(self, sec):
        return sec in self.sections

    def has_key(self, sec, key):
        return (self.has_section(sec) and
                key in self.sections[sec])

    def items(self, sec):
        return self.sections[sec].items()

    def triple_items(self):
        for sec, section in sorted(self.sections.items()):
            for key, value in sorted(section.items()):
                yield sec, key, value

    def clear(self):
        self.sections = {}

    def dump_json(self):
        return json_pp(self.sections)

    def compare_sections(self, new_sections):
        new_vset = set()
        vset = set()
        for sec, section in sorted(new_sections.items()):
            for key, value in sorted(section.items()):
                value = json_to_str(value)
                new_vset.add((sec, key, value))

        for sec, section in sorted(self.sections.items()):
            for key, value in sorted(section.items()):
                value = json_to_str(value)
                vset.add((sec, key, value))

        will_delete = vset - new_vset
        will_add = new_vset - vset

        new_2set = set((sec, key)
                       for (sec, key, value)
                       in will_add)

        will_delete = set((sec, key, value)
                      for (sec, key, value)
                      in will_delete
                      if (sec, key) not in new_2set)
        return will_delete, will_add

_shared = SharedConfig()
def get_sharedconfig():
    return _shared
