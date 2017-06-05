import logging
import re
import random
import json
import time
import asyncio
import aio_etcd as etcd
import aiohttp
from collections import defaultdict
from aiobbox.utils import json_to_str
from aiobbox.exceptions import RegisterFailed, ETCDError
from .etcd_client import EtcdClient
from .cfg import SharedConfig, get_sharedconfig

class ClientAgent(EtcdClient):
    def __init__(self):
        super(ClientAgent, self).__init__()
        self.state = 'INIT'

    async def start(self):
        self.route = defaultdict(list)
        self.boxes = {}
        
        self.connect()

        await self.get_boxes()
        await self.get_configs()
    
        asyncio.ensure_future(self.watch_boxes())
        asyncio.ensure_future(self.watch_configs())
        self.state = 'STARTED'
        
    async def get_boxes(self, chg=None):
        new_route = defaultdict(list)
        boxes = {}
        try:
            r = await self.read(self.path('boxes'),
                                recursive=True)
            for v in self.walk(r):
                m = re.match(r'/[^/]+/boxes/(?P<box>[^/]+)$', v.key)
                if not m:
                    continue
                box_info = json.loads(v.value)
                bind = box_info['bind']
                boxes[bind] = box_info
                for srv in box_info['services']:
                    new_route[srv].append(bind)
        except etcd.EtcdKeyNotFound:
            pass
        self.route = new_route
        self.boxes = boxes
        
    def get_box(self, srv):
        boxes = self.route[srv]
        return random.choice(boxes)

    async def watch_boxes(self):
        return await self.watch_changes('boxes', self.get_boxes)
    
    # config related
    async def set_config(self, sec, key, value):
        assert sec and key
        assert '/' not in sec
        assert '/' not in key

        shared_cfg = get_sharedconfig()
        etcd_key = self.path('configs/{}/{}'.format(sec, key))
        old_value = shared_cfg.get(sec, key)
        value_json = json_to_str(value)
        if old_value:
            old_value_json = json_to_str(old_value)
            await self.write(etcd_key, value_json,
                             prevValue=old_value_json)
        else:
            await self.write(etcd_key, value_json,
                             prevExist=False)
        shared_cfg.set(sec, key, value)        

    async def del_config(self, sec, key):
        assert sec and key
        assert '/' not in sec
        assert '/' not in key
        
        get_sharedconfig().delete(sec, key)
        etcd_key = self.path('configs/{}/{}'.format(sec, key))
        await self.delete(etcd_key)

    async def del_section(self, sec):
        assert sec
        assert '/' not in sec
        
        get_sharedconfig().delete_section(sec)
        etcd_key = self.path('configs/{}'.format(sec))
        await self.delete(etcd_key, recursive=True)
        
    async def clear_config(self):
        get_sharedconfig().clear()
        etcd_key = self.path('configs')
        try:
            await self.delete(etcd_key, recursive=True)
        except etcd.EtcdKeyNotFound:
            logging.debug(
                'key %s not found on delete', etcd_key)
        
    async def get_configs(self, chg=None):
        reg = r'/(?P<prefix>[^/]+)/configs/(?P<sec>[^/]+)/(?P<key>[^/]+)'        
        try:
            r = await self.read(self.path('configs'),
                                recursive=True)
            new_conf = SharedConfig()
            for v in self.walk(r):
                m = re.match(reg, v.key)
                if m:
                    assert m.group('prefix') == self.prefix
                    sec = m.group('sec')
                    key = m.group('key')
                    new_conf.set(sec, key, json.loads(v.value))
                    
            get_sharedconfig().replace_with(new_conf)
        except etcd.EtcdKeyNotFound:
            pass
        except ETCDError:
            pass
        
    async def watch_configs(self):
        return await self.watch_changes('configs', self.get_configs)

_agent = ClientAgent()
def get_cluster():
    return _agent

    