import logging
import uuid
import re
import random
import asyncio
import aio_etcd as etcd
from aio_etcd.lock import Lock
import aiohttp
from collections import defaultdict
from aiobbox.exceptions import ETCDError
from .ticket import get_ticket

logger = logging.getLogger('bbox')

class EtcdClient:
    def path(self, p):
        cfg = get_ticket()
        if p.startswith('/'):
            return '/{}{}'.format(cfg.prefix, p)
        else:
            return '/{}/{}'.format(cfg.prefix, p)

    @property
    def prefix(self):
        return get_ticket().prefix

    def connect(self):
        self.client = None
        self.client_failed = False
        self.cont = True

        etcd_list = get_ticket().etcd
        if len(etcd_list) == 1:
            host, port = etcd_list[0].split(':')
            self.client = etcd.Client(
                host=host,
                port=int(port),
                allow_reconnect=True,
                allow_redirect=True)
        else:
            def split_addr(e):
                host, port = e.split(':')
                return host, int(port)

            host = tuple(split_addr(e)
                         for e in etcd_list)
            self.client = etcd.Client(
                host=host,
                allow_reconnect=True,
                allow_redirect=True)

    def close(self):
        if self.client:
            self.client.close()
        self.cont = False

    # etcd client wraps
    async def _wrap_etcd(self, fn, *args, **kw):
        try:
            r = await fn(*args, **kw)
            self.client_failed = False
            return r
        except aiohttp.ClientError as e:
            logger.warn('http client error', exc_info=True)
            self.client_failed = True
            raise ETCDError
        except etcd.EtcdConnectionFailed:
            #import traceback
            #traceback.print_exc()
            logger.warn('connection failed')
            self.client_failed = True
            raise ETCDError

    async def write(self, *args, **kw):
        return await self._wrap_etcd(self.client.write,
                                     *args, **kw)

    async def read(self, *args, **kw):
        return await self._wrap_etcd(self.client.read,
                                     *args, **kw)

    async def refresh(self, *args, **kw):
        return await self._wrap_etcd(self.client.refresh,
                                     *args, **kw)

    async def delete(self, *args, **kw):
        return await self._wrap_etcd(self.client.delete,
                                     *args, **kw)

    def walk(self, v):
        yield v
        for c in v.children:
            if c.key == v.key:
                continue
            for cc in self.walk(c):
                yield cc

    async def watch_changes(self, component, changed):
        last_index = None
        while self.cont:
            logger.debug('watching %s', component)
            try:
                # watch every 1 min to
                # avoid timeout exception
                chg = await asyncio.wait_for(
                    self.read(self.path(component),
                              recursive=True,
                              waitIndex=last_index,
                              wait=True),
                    timeout=60)
                last_index = chg.modifiedIndex
                await changed(chg)
            except asyncio.TimeoutError:
                logger.debug(
                    'timeout error during watching %s',
                    component)
            except ETCDError:
                logger.warn('etcd error, sleep for a while')
                await asyncio.sleep(1)
            await changed(None)

    def acquire_lock(self, name):
        #cfg = get_ticket()
        #lock_name = name
        #return Lock(self.client, lock_name)
        return SimpleLock(self, self.path('_lock/{}'.format(name)))

class SimpleLock:
    lock_keys = {}

    @classmethod
    async def close_all_keys(cls, client):
        for key, u in cls.lock_keys.items():
            await client.delete(key)
        cls.lock_keys = {}

    async def __aenter__(self):
        return await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        return await self.release()

    def __init__(self, cc, path):
        self.client = cc
        self.path = path
        self.uuid = uuid.uuid4().hex
        self.key = None
        self.cont = True
        self._acquired = False

    @property
    def is_acquired(self):
        return self._acquired

    async def acquire(self):
        if self.client.client_failed:
            raise ETCDError
        r = await self.client.write(self.path, self.uuid, ttl=5, append=True)
        self.key = r.key
        self.lock_keys[r.key] = self.uuid
        asyncio.ensure_future(self.keep_key())
        await self.wait_key()
        return self

    async def release(self):
        if not self.cont and self.client.client_failed:
            return
        if self.key:
            await self.client.delete(self.key)
            self.lock_keys.pop(self.key, None)
            self.key = None
        else:
            r = await self.client.read(self.path,
                                       recursive=True)
            for n in self.walk(r):
                if n.value == self.uuid:
                    await self.client.delete(n.key)

        self._acquired = False
        self.cont = False

    async def check_acquired(self):
        if self.client.client_failed:
            self.cont = False
            return False
        try:
            r = await self.client.read(self.path,
                                       sorted=True,
                                       recursive=True)
        except ETCDError:
            self.cont = False
            return False
        waiters = []
        for n in self.client.walk(r):
            if self.path == n.key:
                continue
            rest_key = n.key[len(self.path):]
            if re.match(r'/?(?P<name>[^/]+)$', rest_key):
                waiters.append(n.key)
        if waiters:
            # if self.key is the first element
            # then the lock is acquired
            if waiters[0] == self.key:
                self._acquired = True
                return True
        return False

    async def wait_key(self):
        while self.cont and not (await self.check_acquired()):
            try:
                chg = await asyncio.wait_for(
                    self.client.read(self.path,
                                     wait=True,
                                     recursive=True),
                    timeout=20)
            except ETCDError:
                self.cont = False
                continue
            except asyncio.TimeoutError:
                continue
            if (chg.action not in ('delete', 'expire')
                or chg.key > self.key):
                # not interest
                continue

            #await asyncio.sleep(0.1)

    async def keep_key(self):
        while self.cont and self.key:
            try:
                await self.client.refresh(self.key, ttl=5)
            except etcd.EtcdKeyNotFound:
                pass
            except ETCDError:
                await self.release()
                #loop = asyncio.get_event_loop()
                #loop.stop()
                break
            await asyncio.sleep(1)
